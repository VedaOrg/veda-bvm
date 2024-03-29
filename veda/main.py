import argparse
import asyncio
import logging
import multiprocessing
import os
import shutil
import signal
import sys
from typing import Callable, Tuple, Type, Sequence, cast, Dict

import argcomplete as argcomplete
from asyncio_run_in_process import open_in_process
from async_service import AsyncioManager
from eth_utils import ValidationError, setup_DEBUG2_logging, get_logger

from veda._utils.ipc import remove_dangling_ipc_files, wait_for_ipc
from veda._utils.logging import IPCListener, set_logger_levels, setup_stderr_logging, setup_file_logging, \
    child_process_logging
from veda.boot_info import BootInfo
from veda.cli_parser import parser, subparser
from veda.config import VedaAppConfig, BaseAppConfig, VedaConfig
from veda.db.backends.level import LevelDB
from veda.db.chain import ChainDB
from veda.db.manager import DBManager
from veda.exceptions import AmbigiousFileSystem, MissingPath
from veda.extensibility import BaseComponentAPI, BaseIsolatedComponent, ComponentAPI, ComponentManager
from veda.initialization import is_database_initialized, initialize_database, is_data_dir_initialized, \
    initialize_data_dir, ensure_veda_dirs
from veda.services.registry import BASE_COMPONENTS

VEDA_HEADER = "\n".join((
    "\n",
    '''      _   __       __    
     | | / /__ ___/ /__ _
     | |/ / -_) _  / _ `/
     |___/\__/\_,_/\_,_/ 
                         
    '''
))

VEDA_AMBIGIOUS_FILESYSTEM_INFO = (
    "Could not initialize data directory\n\n"
    "   One of these conditions must be met:\n"
    "   * HOME environment variable set\n"
    "   * XDG_VEDA_ROOT environment variable set\n"
    "   * VEDA_DATA_DIR environment variable set\n"
    "   * --data-dir command line argument is passed\n"
    "\n"
    "   In case the data directory is outside of the veda root directory\n"
    "   Make sure all paths are pre-initialized as Veda won't attempt\n"
    "   to create directories outside of the veda root directory\n"
)


BootFn = Callable[[BootInfo], Tuple[multiprocessing.Process, ...]]
SubConfigs = Sequence[Type[BaseAppConfig]]


def load_veda_config_from_parser_args(parser: argparse.ArgumentParser,
                                         args: argparse.Namespace,
                                         app_identifier: str,
                                         sub_configs: SubConfigs) -> VedaConfig:
    try:
        return VedaConfig.from_parser_args(args, app_identifier, sub_configs)
    except AmbigiousFileSystem:
        parser.error(VEDA_AMBIGIOUS_FILESYSTEM_INFO)

def ensure_data_dir_is_initialized(veda_config: VedaConfig) -> None:
    if not is_data_dir_initialized(veda_config):
        # TODO: this will only work as is for chains with known genesis
        # parameters.  Need to flesh out how genesis parameters for custom
        # chains are defined and passed around.
        try:
            initialize_data_dir(veda_config)
        except AmbigiousFileSystem:
            parser.error(VEDA_AMBIGIOUS_FILESYSTEM_INFO)
        except MissingPath as e:
            parser.error(
                "\n"
                f"It appears that {e.path} does not exist. "
                "Veda does not attempt to create directories outside of its root path. "
                "Either manually create the path or ensure you are using a data directory "
                "inside the XDG_VEDA_ROOT path"
            )


def configure_parsers(parser: argparse.ArgumentParser,
                      subparser: argparse._SubParsersAction,
                      component_types: Tuple[Type[BaseComponentAPI], ...]) -> None:
    for component_cls in component_types:
        component_cls.configure_parser(parser, subparser)


def parse_and_validate_cli() -> argparse.Namespace:
    argcomplete.autocomplete(parser)

    args = parser.parse_args()

    return args


def resolve_common_log_level_or_error(args: argparse.Namespace) -> str:
    # The `common_log_level` is derived from `--log-level <Level>` / `-l <Level>` without
    # specifying any module. If present, it is used for both `stderr` and `file` logging.
    common_log_level = args.log_levels and args.log_levels.get(None)
    has_ambigous_logging_config = ((
        common_log_level is not None and
        args.stderr_log_level is not None
    ) or (
        common_log_level is not None and
        args.file_log_level is not None
    ))

    if has_ambigous_logging_config:
        parser.error(
            f"""\n
            Ambiguous logging configuration: The `--log-level (-l)` flag sets the
            log level for both file and stderr logging.
            To configure different log level for file and stderr logging,
            remove the `--log-level` flag and use `--stderr-log-level` and/or
            `--file-log-level` separately.
            Alternatively, remove the `--stderr-log-level` and/or `--file-log-level`
            flags to share one single log level across both handlers.
            """
        )
    else:
        return common_log_level


LoggingResult = Tuple[Tuple[logging.Handler, ...], int, Dict[str, int]]


def install_logging(args: argparse.Namespace,
                    veda_config: VedaConfig,
                    common_log_level: str) -> LoggingResult:
    # Setup logging to stderr
    stderr_logger_level = (
        args.stderr_log_level
        if args.stderr_log_level is not None
        else (common_log_level if common_log_level is not None else logging.INFO)
    )
    handler_stderr = setup_stderr_logging(stderr_logger_level)

    # Setup file based logging
    file_logger_level = (
        args.file_log_level
        if args.file_log_level is not None
        else (common_log_level if common_log_level is not None else logging.DEBUG)
    )
    handler_file = setup_file_logging(veda_config.logfile_path, file_logger_level)

    # Set the individual logger levels that have been specified.
    logger_levels = {} if args.log_levels is None else args.log_levels
    # async-service's DEBUG logs completely drowns our stuff (i.e. more than 95% of all our DEBUG
    # logs), so unless explicitly overridden, we limit it to INFO.
    if 'async_service' not in logger_levels:
        logger_levels['async_service'] = logging.INFO
    set_logger_levels(logger_levels)

    min_log_level = min(
        stderr_logger_level,
        file_logger_level,
        *logger_levels.values(),
    )
    # We need to use our minimum level on the root logger to ensure anything logged via a
    # sub-logger using the default level will reach all our handlers. The handlers will then filter
    # those based on their configured levels.
    logger = logging.getLogger()
    logger.setLevel(min_log_level)

    return (handler_stderr, handler_file), min_log_level, logger_levels


def validate_component_cli(component_types: Tuple[Type[BaseComponentAPI], ...],
                           boot_info: BootInfo) -> None:
    # Let the components do runtime validation
    for component_cls in component_types:
        try:
            component_cls.validate_cli(boot_info)
        except ValidationError as exc:
            parser.exit(message=str(exc))


async def run_db_manager(
        boot_info: BootInfo,
        get_base_db_fn: Callable[[BootInfo], LevelDB]) -> None:
    with child_process_logging(boot_info):
        veda_config = boot_info.veda_config
        manager = DBManager(get_base_db_fn(boot_info))
        with veda_config.process_id_file('database'):
            with manager.run(veda_config.database_ipc_path):
                loop = asyncio.get_event_loop()
                try:
                    await loop.run_in_executor(None, manager.wait_stopped)
                finally:
                    # We always need to call stop() before returning as asyncio can't cancel the
                    # thread started by run_in_executor() and that would prevent
                    # open_in_process(run_db_manager, ...) from returning.
                    manager.stop()



async def _run(
        boot_info: BootInfo,
        get_base_db_fn: Callable[[BootInfo], LevelDB],
        component_manager: AsyncioManager) -> None:
    logger = logging.getLogger('veda')
    start_new_session = True
    if os.getenv('VEDA_SINGLE_PROCESS_GROUP') == "1":
        # This is needed because some of our integration tests rely on all processes being in
        # a single process group.
        start_new_session = False
    async with open_in_process(
            run_db_manager,
            boot_info,
            get_base_db_fn,
            subprocess_kwargs={'start_new_session': start_new_session},
    ) as db_proc:
        logger.info("Started DB server process (pid=%d)", db_proc.pid)
        try:
            wait_for_ipc(boot_info.veda_config.database_ipc_path)
        except TimeoutError:
            logger.error("Timeout waiting for database to start.  Exiting...")
            argparse.ArgumentParser().error(message="Timed out waiting for database start")
            return None

        try:
            await component_manager.run()
        finally:
            try:
                await component_manager.stop()
            finally:
                logger.info("Terminating DB process")
                db_proc.send_signal(signal.SIGINT)


def run(component_types: Tuple[Type[BaseComponentAPI], ...],
        boot_info: BootInfo,
        get_base_db_fn: Callable[[BootInfo], LevelDB]) -> None:
    runtime_component_types = tuple(
        cast(Type[BaseIsolatedComponent], component_cls)
        for component_cls in component_types
        if issubclass(component_cls, ComponentAPI)
    )

    veda_config = boot_info.veda_config

    component_manager_service = ComponentManager(
        boot_info,
        runtime_component_types,
    )
    component_manager_manager = AsyncioManager(component_manager_service)

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(
        signal.SIGTERM,
        component_manager_manager.cancel,
        'SIGTERM',
    )
    loop.add_signal_handler(
        signal.SIGINT,
        component_manager_service.shutdown,
        'CTRL+C',
    )

    logger = logging.getLogger()
    try:
        loop.run_until_complete(_run(boot_info, get_base_db_fn, component_manager_manager))
    except BaseException:
        logger.exception("Error during veda run")
        raise
    finally:
        reason = component_manager_service.reason
        hint = f" ({reason})" if reason else f""
        logger.info('Shutting down Veda%s', hint)
        remove_dangling_ipc_files(logger, veda_config.ipc_dir)
        argparse.ArgumentParser().exit(message=f"Veda shutdown complete{hint}\n")
        if veda_config.veda_tmp_root_dir:
            shutil.rmtree(veda_config.veda_root_dir)


BootPrologueData = Tuple[BootInfo, Tuple[logging.Handler, ...]]


def construct_boot_info(app_identifier: str,
                        component_types: Tuple[Type[BaseComponentAPI], ...],
                        sub_configs: Sequence[Type[BaseAppConfig]]) -> BootPrologueData:
    configure_parsers(parser, subparser, component_types)

    args = parse_and_validate_cli()

    common_log_level = resolve_common_log_level_or_error(args)

    veda_config = load_veda_config_from_parser_args(parser,
                                                          args,
                                                          app_identifier,
                                                          sub_configs)

    ensure_data_dir_is_initialized(veda_config)
    handlers, min_log_level, logger_levels = install_logging(
        args,
        veda_config,
        common_log_level
    )

    boot_info = BootInfo(
        args=args,
        veda_config=veda_config,
        min_log_level=min_log_level,
        logger_levels=logger_levels,
        profile=bool(args.profile),
    )

    validate_component_cli(component_types, boot_info)

    return boot_info, handlers


def main_entry(veda_boot: BootFn,
               get_base_db_fn: Callable[[BootInfo], LevelDB],
               app_identifier: str,
               component_types: Tuple[Type[BaseComponentAPI], ...],
               sub_configs: Sequence[Type[BaseAppConfig]]) -> None:
    boot_info, handlers = construct_boot_info(app_identifier, component_types, sub_configs)
    args = boot_info.args
    veda_config = boot_info.veda_config

    # Components can provide a subcommand with a `func` which does then control
    # the entire process from here.
    if hasattr(args, 'func'):
        args.func(args, veda_config)
        return

    # This prints out the ASCII "veda" header in the terminal
    display_launch_logs(veda_config)

    # Setup the log listener which child processes relay their logs through
    with IPCListener(*handlers).run(veda_config.logging_ipc_path):
        veda_boot(boot_info)
        run(component_types, boot_info, get_base_db_fn)


def display_launch_logs(veda_config: VedaConfig) -> None:
    logger = logging.getLogger('Veda')
    logger.info(VEDA_HEADER)
    logger.info("Started main process (pid=%d)", os.getpid())
    logger.info("Veda DEBUG log file is created at %s", str(veda_config.logfile_path))

def main_entry(veda_boot: BootFn,
               get_base_db_fn: Callable[[BootInfo], LevelDB],
               app_identifier: str,
               component_types: Tuple[Type[BaseComponentAPI], ...],
               sub_configs: Sequence[Type[BaseAppConfig]]) -> None:
    boot_info, handlers = construct_boot_info(app_identifier, component_types, sub_configs)
    args = boot_info.args
    veda_config = boot_info.veda_config

    # Components can provide a subcommand with a `func` which does then control
    # the entire process from here.
    if hasattr(args, 'func'):
        args.func(args, veda_config)
        return

    # This prints out the ASCII "veda" header in the terminal
    display_launch_logs(veda_config)

    # Setup the log listener which child processes relay their logs through
    with IPCListener(*handlers).run(veda_config.logging_ipc_path):
        veda_boot(boot_info)
        run(component_types, boot_info, get_base_db_fn)


def get_base_db(boot_info: BootInfo) -> LevelDB:
    app_config = boot_info.veda_config.get_app_config(VedaAppConfig)
    base_db = LevelDB(db_path=app_config.database_dir)
    chaindb = ChainDB(base_db)
    if not is_database_initialized(chaindb):
        chain_config = app_config.get_chain_config()
        initialize_database(chain_config, chaindb, base_db)
    return base_db

def veda_boot_fn(boot_info: BootInfo) -> None:
    veda_config = boot_info.veda_config
    ensure_veda_dirs(veda_config.get_app_config(VedaAppConfig))

def main():
    os.environ['ASYNCIO_RUN_IN_PROCESS_STARTUP_TIMEOUT'] = '3000'

    main_entry(
        veda_boot_fn,
        get_base_db,
        'veda1',
        BASE_COMPONENTS,
        (VedaAppConfig,)
    )

if __name__ == '__main__':
    main()
