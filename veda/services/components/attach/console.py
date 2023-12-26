import code
import contextlib
from functools import partial
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterator, cast,
)

from eth_utils import encode_hex
from eth_utils.toolz import merge

from veda.abc import AtomicDatabaseAPI
from veda.chains.base import MiningChain
from veda.chains.veda import VedaChain
from veda.db.chain import ChainDB
from veda.db.backends.level import LevelDB

from web3.types import RPCEndpoint, RPCResponse

from veda.config import (
    VedaAppConfig,
    VedaConfig,
)
from veda.db.manager import DBClient
from veda.vm.forks.veda import VedaBlockHeader


def create_missing_ipc_error_message(ipc_path: Path) -> str:
    log_message = (
        f"The IPC path at {str(ipc_path)} is not found. \n"
        "Please run "
        "'veda --data-dir <path-to-running-nodes-data-dir> attach' "
        "or 'veda attach <path-to-jsonrpc.ipc>'"
        "to specify the IPC path."
    )
    return log_message

DEFAULT_BANNER: str = (
    "Veda Console\n"
    "---------------\n"
    "An instance of Web3 connected to the running chain is available as the "
    "`w3` variable\n"
    "The exposed `rpc` function allows raw RPC API calls (e.g. rpc('net_listening'))\n"
)

DB_SHELL_BANNER: str = (
    "Veda DB Shell\n"
    "---------------\n"
    "An instance of `ChainDB` connected to the database is available as the "
    "`chaindb` variable\n"
)


def ipython_shell(namespace: Dict[str, Any], banner: str) -> Any:
    """Try to run IPython shell."""
    try:
        import IPython
    except ImportError:
        raise ImportError(
            "The IPython library is not available.  Make sure IPython is "
            "installed or re-run with --vanilla-shell"
        )

    return IPython.terminal.embed.InteractiveShellEmbed(
        user_ns=namespace,
        banner1=banner,
    )


def python_shell(namespace: Dict[str, Any], banner: str) -> Any:
    """Start a vanilla Python REPL shell."""
    try:
        import readline, rlcompleter  # noqa: F401, E401
    except ImportError:
        pass
    else:
        readline.parse_and_bind('tab: complete')

    shell = code.InteractiveConsole(namespace)
    return partial(shell.interact, banner=banner)


def console(ipc_path: Path,
            use_ipython: bool = True,
            env: Dict[str, Any] = None,
            banner: str = DEFAULT_BANNER) -> None:
    """
    Method that starts the chain, setups the veda CLI and register the
    cleanup function.
    """
    if env is None:
        env = {}

    # if ipc_path is not found, raise an exception with a useful message
    if not ipc_path.exists():
        raise FileNotFoundError(create_missing_ipc_error_message(ipc_path))

    # wait to import web3, because it's somewhat large, and not usually used
    import web3
    ipc_provider = web3.IPCProvider(ipc_path)
    w3 = web3.Web3(ipc_provider)

    # Allow omitting params by defaulting to `None`
    def rpc(method: RPCEndpoint, params: Dict[str, Any] = None) -> RPCResponse:
        return ipc_provider.make_request(method, params)

    namespace = merge({'w3': w3, 'rpc': rpc}, env)

    shell(use_ipython, namespace, banner)


def db_shell(use_ipython: bool, config: Dict[str, str]) -> None:
    has_mining_chain = 'mining_chain' in config
    mining_chain_text = '- `mining_chain: `MiningChain` instance. (use a REPL to create blocks)'

    greeter = f"""
    Veda Block Number: #{config['veda_block_number']}
    Veda Block Hash: {encode_hex(config['veda_block_hash'])}
    Veda Prevrandao: {encode_hex(config['mix_hash'])}
    Veda Timestamp: {config['veda_timestamp']}
    
    Head: #{config['block_number']}
    Hash: {config['hex_hash']}
    State Root: {config['state_root_hex']}
    
    Inspecting active Veda? {config['veda_already_running']}

    Available Context Variables:
      - `db`: base database object
      - `chaindb`: `ChainDB` instance
      - `veda_config`: `VedaConfig` instance
      - `chain_config`: `ChainConfig` instance
      - `chain`: `Chain` instance
      {mining_chain_text if has_mining_chain else ''}
    """

    namespace = {
        'db': config.get("db"),
        'chaindb': config.get("chaindb"),
        'veda_config': config.get("veda_config"),
        'chain_config': config.get("chain_config"),
        'chain': config.get("chain"),
    }

    if has_mining_chain:
        namespace['mining_chain'] = config.get('mining_chain')

    shell(use_ipython, namespace, DB_SHELL_BANNER + greeter)


@contextlib.contextmanager
def _get_base_db(database_dir: Path, ipc_path: Path) -> Iterator[AtomicDatabaseAPI]:
    veda_already_running = ipc_path.exists()
    if veda_already_running:
        db = DBClient.connect(ipc_path)
        with db:
            yield db
    else:
        yield LevelDB(database_dir)


@contextlib.contextmanager
def get_veda_shell_context(database_dir: Path,
                           veda_config: VedaConfig) -> Iterator[Dict[str, Any]]:
    app_config = veda_config.get_app_config(VedaAppConfig)
    ipc_path = veda_config.database_ipc_path
    veda_already_running = ipc_path.exists()

    with _get_base_db(database_dir, ipc_path) as db:
        chaindb = ChainDB(db)
        head = chaindb.get_canonical_head()
        chain_config = app_config.get_chain_config()
        chain = chain_config.full_chain_class(db)

        veda_chain = cast(VedaChain, chain)
        veda_head = cast(VedaBlockHeader, head)
        yield {
            'db': db,
            'chaindb': chaindb,
            'veda_config': veda_config,
            'chain_config': chain_config,
            'chain': chain,
            'block_number': head.block_number,
            'hex_hash': head.hex_hash,
            'veda_chain': veda_chain,
            'veda_block_number': veda_head.veda_block_number,
            'veda_block_hash': veda_head.veda_block_hash,
            'veda_timestamp': veda_head.veda_timestamp,
            'mix_hash': veda_head.mix_hash,
            'state_root_hex': encode_hex(head.state_root),
            'veda_already_running': veda_already_running,
        }


def shell(use_ipython: bool, namespace: Dict[str, Any], banner: str) -> None:
    if use_ipython:
        ipython_shell(namespace, banner)()
    else:
        python_shell(namespace, banner)()
