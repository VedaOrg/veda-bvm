from abc import (
    ABC,
    abstractmethod,
)
import argparse
from contextlib import (
    contextmanager,
)
from enum import (
    Enum,
    auto,
)
import json
from pathlib import (
    Path,
)
from typing import (   # noqa: F401
    Any,
    Dict,
    Iterable,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from eth_utils import encode_hex

from veda.abc import (
    AtomicDatabaseAPI,
)
from veda.rpc.chain import VedaAsyncChain
from veda.constants import VEDA_NETWORK_ID, GENESIS_BLOCK_NUMBER

from veda.typing import (
    VMConfiguration,
)
from eth_keys import (
    keys,
)
from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    Address, BlockNumber,
)

from veda._utils.chains import (
    construct_veda_config_params,
    get_database_socket_path,
    get_jsonrpc_socket_path,
    get_nodekey_path,
    load_nodekey,
)
from veda._utils.eip1085 import (
    Account,
    GenesisData,
    GenesisParams,
    extract_genesis_data,
)
from veda._utils.filesystem import (
    PidFile,
)
from veda._utils.xdg import (
    get_xdg_veda_root,
)
from veda.constants import (
    ASSETS_DIR,
    IPC_DIR,
    LOG_DIR,
    LOG_FILE,
    ENR_DB_DIR,
    PID_DIR,
    SYNC_LIGHT,
)

DATABASE_DIR_NAME = 'chain'
LOGGING_IPC_SOCKET_FILENAME = 'logging.ipc'


class VedaChainConfig:
    def __init__(self,
                 genesis_data: GenesisData,
                 chain_name: str = None) -> None:

        self.genesis_data = genesis_data
        self._chain_name = chain_name

    @property
    def chain_name(self) -> str:
        if self._chain_name is None:
            return "VedaChain"
        else:
            return self._chain_name

    @property
    def full_chain_class(self) -> Type['FullChain']:

        return VedaAsyncChain.configure(
            __name__=self.chain_name,
            vm_configuration=self.vm_configuration,
            chain_id=self.chain_id,
        )

    @property
    def light_chain_class(self) -> Type['LightDispatchChain']:

        return VedaAsyncChain.configure(
            __name__=self.chain_name,
            vm_configuration=self.vm_configuration,
            chain_id=self.chain_id,
        )

    @classmethod
    def from_genesis_config(cls,
                            genesis_config: Dict[str, Any],
                            chain_name: str = None,
                            ) -> 'VedaChainConfig':
        genesis_data = extract_genesis_data(genesis_config)
        return cls(
            genesis_data=genesis_data,
            chain_name=chain_name,
        )

    @property
    def chain_id(self) -> int:
        return self.genesis_data.chain_id

    @property
    def genesis_params(self) -> GenesisParams:
        """
        Return the genesis configuation parsed from the genesis configuration file.
        """
        return self.genesis_data.params

    @property
    def genesis_state(self) -> Dict[Address, Account]:
        return self.genesis_data.state

    def initialize_chain(self,
                         base_db: AtomicDatabaseAPI) -> 'FullChain':
        genesis_params = self.genesis_params.to_dict()
        genesis_state = {
            address: account.to_dict()
            for address, account
            in self.genesis_state.items()
        }
        return cast('FullChain', self.full_chain_class.from_genesis(
            base_db=base_db,
            genesis_params=genesis_params,
            genesis_state=genesis_state,
        ))

    @property
    def vm_configuration(self) -> VMConfiguration:
        """
        Return the vm configuration specifed from the genesis configuration file.
        """
        # return self.apply_consensus_engine(self.genesis_data.vm_configuration)
        return self.genesis_data.vm_configuration


TAppConfig = TypeVar('TAppConfig', bound='BaseAppConfig')

class VedaConfig:
    """
    The :class:`~veda.config.VedaConfig` holds all base configurations that are generic
    enough to be shared across the different runtime modes that are available. It also gives access
    to the more specific application configurations derived from
    :class:`~veda.config.BaseAppConfig`.

    This API is exposed to :class:`~veda.extensibility.component.BaseComponent`
    """

    _veda_root_dir: Path = None

    _chain_config: VedaChainConfig = None

    _data_dir: Path = None
    _logfile_path: Path = None
    _network_id: int = None

    port: int = None

    _genesis_config: Dict[str, Any] = None

    _app_configs: Dict[Type['BaseAppConfig'], 'BaseAppConfig'] = None

    def __init__(self,
                 app_identifier: str = "VedaSync",
                 genesis_config: Dict[str, Any] = None,
                 veda_root_dir: Path = None,
                 veda_tmp_root_dir: bool = False,
                 data_dir: Path = None,
                 port: int = 30303) -> None:
        # TODO: VEDA - 移除 nodekey 和 genesis_config 相关
        self.app_identifier = app_identifier
        self.network_id = VEDA_NETWORK_ID
        self.port = port
        self._app_configs = {}

        if genesis_config is not None:
            self.genesis_config = genesis_config
        else:
            self.genesis_config = \
                {'genesis': {
                    'nonce': '0x0000000000000000',
                    'difficulty': '0x00',
                    'extraData': '0x00',
                    # 'coinbase': encode_hex(b'\x00' * 20),
                    'gasLimit': '0x7A1200',
                    'author': '0x00',
                    'timestamp': '0x6564e696',
                    'veda_block_number': BlockNumber(GENESIS_BLOCK_NUMBER),
                    'veda_timestamp': '0x00',
                    'veda_block_hash': encode_hex(b'\x00' * 32),
                },
                    'params': {
                        'vedaForkBlock': '0x00',
                        'chainId': '0x01'
                    }
                }
        # else:
        #     raise TypeError(
        #         "No `genesis_config` was provided and the `network_id` is not "
        #         "in the known preconfigured networks.  Cannot initialize "
        #         "ChainConfig"
        #     )

        if veda_root_dir is not None:
            self.veda_root_dir = veda_root_dir
        self.veda_tmp_root_dir = veda_tmp_root_dir

        if data_dir is not None:
            self.data_dir = data_dir

    @property
    def app_suffix(self) -> str:
        """
        Return the suffix that Veda uses to derive various application directories depending
        on the current mode of operation (e.g. ``veda`` to derive
        ``<veda-root-dir>/mainnet/logs-veda``)
        """
        return "" if len(self.app_identifier) == 0 else f"-{self.app_identifier}"

    @property
    def logfile_path(self) -> Path:
        """
        Return the path to the log file.
        """
        return self.log_dir / LOG_FILE

    @property
    def log_dir(self) -> Path:
        """
        Return the path of the directory where all log files are stored.
        """
        return self.with_app_suffix(self.data_dir / LOG_DIR)

    @property
    def veda_root_dir(self) -> Path:
        """
        Base directory that all veda data is stored under.

        The default ``data_dir`` path will be resolved relative to this
        directory.
        """
        if self._veda_root_dir is not None:
            return self._veda_root_dir
        else:
            return get_xdg_veda_root()

    @veda_root_dir.setter
    def veda_root_dir(self, value: str) -> None:
        self._veda_root_dir = Path(value).resolve()

    @property
    def data_dir(self) -> Path:
        """
        The data_dir is the base directory that all chain specific information
        for a given chain is stored.

        All defaults for chain directories are resolved relative to this
        directory.
        """
        if self._data_dir is not None:
            return self._data_dir
        else:
            raise TypeError("No `data_dir` was provided")

    @data_dir.setter
    def data_dir(self, value: str) -> None:
        self._data_dir = Path(value).resolve()

    @property
    def database_ipc_path(self) -> Path:
        """
        Return the path for the database IPC socket connection.
        """
        return get_database_socket_path(self.ipc_dir)

    @property
    def enr_db_dir(self) -> Path:
        """
        Return the directory for the Node database.
        """
        return self.with_app_suffix(self.data_dir / ENR_DB_DIR)

    @property
    def logging_ipc_path(self) -> Path:
        """
        Return the path for the logging IPC socket connection.
        """
        return self.ipc_dir / LOGGING_IPC_SOCKET_FILENAME

    @property
    def ipc_dir(self) -> Path:
        """
        Return the base directory for all open IPC files.
        """
        return self.with_app_suffix(self.data_dir / IPC_DIR)

    @property
    def pid_dir(self) -> Path:
        """
        Return the base directory for all PID files.
        """
        return self.with_app_suffix(self.data_dir / PID_DIR)

    @property
    def jsonrpc_ipc_path(self) -> Path:
        """
        Return the path for the JSON-RPC server IPC socket.
        """
        return get_jsonrpc_socket_path(self.ipc_dir)

    @property
    def internal_jsonrpc_ipc_path(self) -> Path:
        """
        Return the path for the internal JSON-RPC server IPC socket.
        """
        return self.ipc_dir / 'internal.ipc'

    @property
    def nodekey_path(self) -> Path:
        """
        Path where the nodekey is stored
        """
        if self._nodekey_path is None:
            if self._nodekey is not None:
                return None
            else:
                return get_nodekey_path(self.data_dir)
        else:
            return self._nodekey_path

    @contextmanager
    def process_id_file(self, process_name: str):  # type: ignore
        """
        Context manager API to generate process identification files (pid) in the current
        :meth:`pid_dir`.

        .. code-block:: python

            veda_config.process_id_file('networking'):
                ... # pid file sitting in pid directory while process is running
            ... # pid file cleaned up
        """
        with PidFile(process_name, self.pid_dir):
            yield

    @classmethod
    def from_parser_args(cls,
                         parser_args: argparse.Namespace,
                         app_identifier: str,
                         app_config_types: Iterable[Type['BaseAppConfig']]) -> 'VedaConfig':
        """
        Initialize a :class:`~veda.config.VedaConfig` from the namespace object produced by
        an :class:`~argparse.ArgumentParser`.
        """
        constructor_kwargs: dict = construct_veda_config_params(parser_args)
        veda_config = cls(app_identifier=app_identifier, **constructor_kwargs)

        veda_config.initialize_app_configs(parser_args, app_config_types)

        return veda_config

    def initialize_app_configs(self,
                               parser_args: argparse.Namespace,
                               app_config_types: Iterable[Type['BaseAppConfig']]) -> None:
        """
        Initialize :class:`~veda.config.BaseAppConfig` instances for the passed
        ``app_config_types`` based on the ``parser_args`` and the existing
        :class:`~veda.config.TrintiyConfig` instance.
        """
        for app_config_type in app_config_types:
            self.add_app_config(app_config_type.from_parser_args(parser_args, self))

    def add_app_config(self, app_config: 'BaseAppConfig') -> None:
        """
        Register the given ``app_config``.
        """
        self._app_configs[type(app_config)] = app_config

    def has_app_config(self, app_config_type: Type['BaseAppConfig']) -> bool:
        """
        Check if a :class:`~veda.config.BaseAppConfig` instance exists that matches the given
        ``app_config_type``.
        """
        return app_config_type in self._app_configs.keys()

    def get_app_config(self, app_config_type: Type[TAppConfig]) -> TAppConfig:
        """
        Return the registered :class:`~veda.config.BaseAppConfig` instance that matches
        the given ``app_config_type``.
        """
        # We want this API to return the specific type of the app config that is requested.
        # Our backing field only knows that it is holding `BaseAppConfig`'s but not concrete types
        return cast(TAppConfig, self._app_configs[app_config_type])

    def with_app_suffix(self, path: Path) -> Path:
        """
        Return a :class:`~pathlib.Path` that matches the given ``path`` plus the :meth:`app_suffix`
        """
        return path.with_name(path.name + self.app_suffix)


class BaseAppConfig(ABC):

    def __init__(self, veda_config: VedaConfig):
        self.veda_config = veda_config

    @classmethod
    @abstractmethod
    def from_parser_args(cls,
                         args: argparse.Namespace,
                         veda_config: VedaConfig) -> 'BaseAppConfig':
        """
        Initialize from the namespace object produced by
        an ``argparse.ArgumentParser`` and the :class:`~veda.config.VedaConfig`
        """
        pass


class VedaAppConfig(BaseAppConfig):

    def __init__(self, veda_config: VedaConfig, sync_mode: str):
        super().__init__(veda_config)
        self.veda_config = veda_config
        self._sync_mode = sync_mode

    @classmethod
    def from_parser_args(cls,
                         args: argparse.Namespace,
                         veda_config: VedaConfig) -> 'BaseAppConfig':
        """
        Initialize from the namespace object produced by
        an ``argparse.ArgumentParser`` and the :class:`~veda.config.VedaConfig`
        """
        return cls(veda_config, 'full')

    @property
    def database_dir(self) -> Path:
        """
        Path where the chain database is stored.

        This is resolved relative to the ``data_dir``
        """
        path = self.veda_config.data_dir / DATABASE_DIR_NAME
        return self.veda_config.with_app_suffix(path) / "full"

    def get_chain_config(self) -> VedaChainConfig:
        """
        Return the :class:`~veda.config.Eth1ChainConfig` either derived from the ``network_id``
        or a custom genesis file.
        """
        # the `ChainConfig` object cannot be pickled so we can't cache this
        # value since the VedaConfig is sent across process boundaries.
        return VedaChainConfig.from_genesis_config(self.veda_config.genesis_config)

    @property
    def sync_mode(self) -> str:
        """
        Return the currently used sync mode
        """
        return self._sync_mode
