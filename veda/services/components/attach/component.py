from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import logging
import pkg_resources
import sys
import pathlib

from veda.config import (
    BaseAppConfig,
    VedaAppConfig,
    VedaConfig,
)
from veda.extensibility import (
    Application,
)

from veda.services.components.attach.console import (
    console,
    db_shell,
    get_veda_shell_context,
)


def is_ipython_available() -> bool:
    try:
        pkg_resources.get_distribution('IPython')
    except pkg_resources.DistributionNotFound:
        return False
    else:
        return True


class AttachComponent(Application):
    logger = logging.getLogger('veda.components.attach.Attach')

    @classmethod
    def configure_parser(cls,
                         arg_parser: ArgumentParser,
                         subparser: _SubParsersAction) -> None:

        attach_parser = subparser.add_parser(
            'attach',
            help='open an REPL attached to a currently running chain',
        )
        attach_parser.add_argument(
            'ipc_path',
            nargs='?',
            type=pathlib.Path,
            help='Specify an IPC path'
        )

        attach_parser.set_defaults(func=cls.run_console)

    @classmethod
    def run_console(cls, args: Namespace, veda_config: VedaConfig) -> None:
        try:
            ipc_path = args.ipc_path or veda_config.jsonrpc_ipc_path
            console(ipc_path, use_ipython=is_ipython_available())
        except FileNotFoundError as err:
            cls.logger.error(str(err))
            sys.exit(1)


class DbShellComponent(Application):
    logger = logging.getLogger('veda.components.attach.DbShell')

    @classmethod
    def configure_parser(cls,
                         arg_parser: ArgumentParser,
                         subparser: _SubParsersAction) -> None:

        attach_parser = subparser.add_parser(
            'db-shell',
            help='open a REPL to inspect the db',
        )
        attach_parser.set_defaults(func=cls.run_shell)

    @classmethod
    def run_shell(cls, args: Namespace, veda_config: VedaConfig) -> None:
        config: BaseAppConfig

        if veda_config.has_app_config(VedaAppConfig):
            config = veda_config.get_app_config(VedaAppConfig)
            with get_veda_shell_context(config.database_dir, veda_config) as context:
                db_shell(is_ipython_available(), context)
        else:
            cls.logger.error(
                "DB Shell only supports Ethereum 1 nodes at this time"
            )
