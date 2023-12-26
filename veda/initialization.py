import os

from veda.abc import (
    AtomicDatabaseAPI,
    ChainDatabaseAPI,
)
from veda.exceptions import CanonicalHeadNotFound

from veda.config import (
    VedaAppConfig,
    VedaChainConfig,
    VedaConfig,
)
from veda.exceptions import (
    MissingPath,
)
from veda._utils.filesystem import (
    is_under_path,
)


def is_data_dir_initialized(veda_config: VedaConfig) -> bool:
    """
    Return ``True`` if the data directory and all expected sub directories exist,
    otherwise return ``False``
    """

    if not os.path.exists(veda_config.data_dir):
        return False

    if not os.path.exists(veda_config.pid_dir):
        return False

    if not os.path.exists(veda_config.ipc_dir):
        return False

    if not os.path.exists(veda_config.enr_db_dir):
        return False

    if not veda_config.logfile_path.parent.exists():
        return False
    elif not veda_config.logfile_path.exists():
        return False

    return True


def is_database_initialized(chaindb: ChainDatabaseAPI) -> bool:
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # empty chain database
        return False
    else:
        return True


def initialize_data_dir(veda_config: VedaConfig) -> None:
    should_create_data_dir = (
        not veda_config.data_dir.exists() and
        is_under_path(veda_config.veda_root_dir, veda_config.data_dir)
    )
    if should_create_data_dir:
        veda_config.data_dir.mkdir(parents=True, exist_ok=True)
    elif not veda_config.data_dir.exists():
        # we don't lazily create the base dir for non-default base directories.
        raise MissingPath(
            f"The base chain directory provided does not exist: `{str(veda_config.data_dir)}`",
            veda_config.data_dir,
        )

    # Logfile
    should_create_logdir = (
        not veda_config.log_dir.exists() and
        (
            # If we're in the default path, always create the log directory
            is_under_path(veda_config.veda_root_dir, veda_config.log_dir) or
            (
                # If we're in a custom path, create the log directory if the data dir is empty
                is_under_path(veda_config.data_dir, veda_config.log_dir) and
                not any(veda_config.data_dir.iterdir())
            )
        )
    )
    if should_create_logdir:
        veda_config.log_dir.mkdir(parents=True, exist_ok=True)
        veda_config.logfile_path.touch()
    elif not veda_config.log_dir.exists():
        # we don't lazily create the base dir for non-default base directories.
        raise MissingPath(
            "The base logging directory provided does not exist: `{0}`".format(
                veda_config.log_dir,
            ),
            veda_config.log_dir,
        )

    # Initialize chain, pid, ipc and enrdb directories
    os.makedirs(veda_config.pid_dir, exist_ok=True)
    os.makedirs(veda_config.ipc_dir, exist_ok=True)
    os.makedirs(veda_config.enr_db_dir, exist_ok=True)

def initialize_database(chain_config: VedaChainConfig,
                        chaindb: ChainDatabaseAPI,
                        base_db: AtomicDatabaseAPI) -> None:
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        chain_config.initialize_chain(base_db)


def ensure_veda_dirs(app_config: VedaAppConfig) -> None:
    if not app_config.database_dir.exists():
        app_config.database_dir.mkdir(parents=True, exist_ok=True)
