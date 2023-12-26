import argparse
import os
import tempfile
from pathlib import Path
from typing import (
    cast,
    Any,
    Dict,
    Iterable,
    Optional,
    Tuple,
    Union,
)

from mypy_extensions import (
    TypedDict,
)

from eth_utils import (
    decode_hex,
)

from eth_keys import keys
from eth_keys.datatypes import PrivateKey


#
# Filesystem path utils
#
def get_local_data_dir(chain_name: str, veda_root_dir: Path) -> Path:
    """
    Returns the base directory path where data for a given chain will be stored.
    """
    try:
        return Path(os.environ['VEDA_DATA_DIR'])
    except KeyError:
        return veda_root_dir / chain_name

NODEKEY_FILENAME = 'nodekey'


def get_nodekey_path(data_dir: Path) -> Path:
    """
    Returns the path to the private key used for devp2p connections.
    """
    return Path(os.environ.get(
        'VEDA_NODEKEY',
        str(data_dir / NODEKEY_FILENAME),
    ))


DATABASE_SOCKET_FILENAME = 'db.ipc'


def get_database_socket_path(data_dir: Path) -> Path:
    """
    Returns the path to the private key used for devp2p connections.

    We're still returning 'str' here on ipc-related path because an issue with
    multi-processing not being able to interpret 'Path' objects correctly.
    """
    return Path(os.environ.get(
        'VEDA_DATABASE_IPC',
        data_dir / DATABASE_SOCKET_FILENAME,
    ))


JSONRPC_SOCKET_FILENAME = 'jsonrpc.ipc'


def get_jsonrpc_socket_path(data_dir: Path) -> Path:
    """
    Returns the path to the ipc socket for the JSON-RPC server.

    We're still returning 'str' here on ipc-related path because an issue with
    multi-processing not being able to interpret 'Path' objects correctly.
    """
    return Path(os.environ.get(
        'VEDA_JSONRPC_IPC',
        data_dir / JSONRPC_SOCKET_FILENAME,
    ))


#
# Nodekey loading
#
def load_nodekey(nodekey_path: Path) -> PrivateKey:
    with nodekey_path.open('rb') as nodekey_file:
        nodekey_raw = nodekey_file.read()
    nodekey = keys.PrivateKey(nodekey_raw)
    return nodekey


class VedaConfigParams(TypedDict):
    network_id: int

    veda_root_dir: Optional[Path]

    genesis_config: Optional[Dict[str, Any]]

    data_dir: Optional[Path]

    nodekey_path: Optional[Path]
    nodekey: Optional[PrivateKey]

    max_peers: Optional[int]

    port: Optional[int]


def construct_veda_config_params(
        args: argparse.Namespace) -> VedaConfigParams:
    return cast(VedaConfigParams, dict(_construct_veda_config_params(args)))


def _random_symbol_of_length(n: int) -> str:
    import string
    import random
    return "".join(random.choice(string.ascii_letters) for _ in range(n))


def _construct_veda_config_params(
        args: argparse.Namespace
) -> Iterable[Tuple[str, Union[int, str, bytes, Path, Tuple[str, ...]]]]:
    """
    Helper function for constructing the kwargs to initialize a VedaConfig object.
    """
    yield 'veda_tmp_root_dir', args.veda_tmp_root_dir
    if args.veda_tmp_root_dir:
        yield 'veda_root_dir', Path(tempfile.gettempdir()) / Path(_random_symbol_of_length(4))
    elif args.veda_root_dir is not None:
        yield 'veda_root_dir', args.veda_root_dir

    # if args.genesis is not None:
    #     if args.data_dir is None:
    #         raise ValueError("When providing a custom genesis, must also provide a data-dir")
    #     yield 'genesis_config', args.genesis

    if args.data_dir is not None:
        yield 'data_dir', args.data_dir

    if args.port is not None:
        yield 'port', args.port
