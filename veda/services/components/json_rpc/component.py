from argparse import (
    Action,
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import contextlib
from typing import Iterator, Tuple, Sequence, Type, Any

from async_service import Service
from eth_utils import ValidationError, to_tuple

from lahja import EndpointAPI

from veda.db.header import (
    HeaderDB,
)

from veda.config import (
    VedaAppConfig,
    VedaConfig
)
from veda.events import NewBlockImportStarted, NewBlockImportFinished, NewBlockImportCanceled
from veda.rpc.base import AsyncChainAPI
from veda.db.manager import DBClient
from veda.extensibility import (
    AsyncioIsolatedComponent,
)
from veda.rpc.server import (
    RPCServer,
)
from veda.rpc.modules import (
    BaseRPCModule,
    initialize_veda_modules,
)
from veda.rpc.ipc import (
    IPCServer,
)
from veda.http.handlers.rpc_handler import RPCHandler
from veda.http.server import (
    HTTPServer,
)
from veda._utils.services import run_background_asyncio_services


@contextlib.contextmanager
def chain_for_veda_config(veda_config: VedaConfig,
                          veda_app_config: VedaAppConfig,
                          event_bus: EndpointAPI) -> Iterator[AsyncChainAPI]:
    chain_config = veda_app_config.get_chain_config()

    db = DBClient.connect(veda_config.database_ipc_path)

    with db:
        yield chain_config.full_chain_class(db)


@contextlib.contextmanager
def chain_for_config(veda_config: VedaConfig,
                     event_bus: EndpointAPI,
                     ) -> Iterator[AsyncChainAPI]:
    if veda_config.has_app_config(VedaAppConfig):
        veda_app_config = veda_config.get_app_config(VedaAppConfig)
        with chain_for_veda_config(veda_config, veda_app_config, event_bus) as veda_chain:
            yield veda_chain
    else:
        raise Exception("Unsupported Node Type")


ALLOW_ALL_MODULES: Tuple[str, ...] = ('*',)


class NormalizeRPCModulesConfig(Action):
    def __call__(self,
                 parser: ArgumentParser,
                 namespace: Namespace,
                 value: Any,
                 option_string: str = None) -> None:

        normalized_str = value.lower().strip()

        if normalized_str == '*':
            parsed = ALLOW_ALL_MODULES
        else:
            parsed = tuple(module_name.strip() for module_name in normalized_str.split(','))
        setattr(namespace, self.dest, parsed)


@to_tuple
def get_http_enabled_modules(
        enabled_modules: Sequence[str],
        available_modules: Sequence[BaseRPCModule]) -> Iterator[Type[BaseRPCModule]]:
    all_module_types = set(type(mod) for mod in available_modules)

    if enabled_modules == ALLOW_ALL_MODULES:
        yield from all_module_types
    else:
        for module_name in enabled_modules:
            match = tuple(
                mod for mod in available_modules if mod.get_name() == module_name
            )
            if len(match) == 0:
                raise ValidationError(f"Unknown module {module_name}")
            elif len(match) > 1:
                raise ValidationError(
                    f"Invalid, {match} all share identifier {module_name}"
                )
            else:
                yield type(match[0])


class JsonRpcServerComponent(AsyncioIsolatedComponent):
    name = "JSON-RPC API"

    @property
    def is_enabled(self) -> bool:
        return not self._boot_info.args.disable_rpc

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--disable-rpc",
            action="store_true",
            help="Disables the JSON-RPC server",
        )
        arg_parser.add_argument(
            "--enable-rpc-debug-mode",
            action="store_true",
            help="Debug the JSON-RPC server",
        )

        arg_parser.add_argument(
            "--enable-http-apis",
            type=str,
            action=NormalizeRPCModulesConfig,
            default="",
            help=(
                "Enable HTTP access to specified JSON-RPC APIs (e.g. 'veda,net'). "
                "Use '*' to enable HTTP access to all modules (including eth_admin)."
            )
        )
        arg_parser.add_argument(
            "--http-listen-address",
            type=str,
            help="Address for the HTTP server to listen on",
            default="0.0.0.0",
        )
        arg_parser.add_argument(
            "--http-port",
            type=int,
            help="JSON-RPC server port",
            default=8545,
        )


    async def do_run(self, event_bus: EndpointAPI) -> None:
        boot_info = self._boot_info
        veda_config = boot_info.veda_config

        with chain_for_config(veda_config, event_bus) as chain:
            if veda_config.has_app_config(VedaAppConfig):
                modules = initialize_veda_modules(chain, event_bus, veda_config)
            else:
                raise Exception("Unsupported Node Type")

            rpc = RPCServer(modules, chain, event_bus, debug_mode=boot_info.args.enable_rpc_debug_mode)

            event_bus.subscribe(
                NewBlockImportStarted,
                lambda ev: rpc.block_request()
            )

            event_bus.subscribe(
                NewBlockImportFinished,
                lambda ev: rpc.resume_request()
            )

            event_bus.subscribe(
                NewBlockImportCanceled,
                lambda ev: rpc.resume_request()
            )

            # Run IPC Server
            ipc_server = IPCServer(rpc, boot_info.veda_config.jsonrpc_ipc_path)
            services_to_exit: Tuple[Service, ...] = (
                ipc_server,
            )
            try:
                http_modules = get_http_enabled_modules(boot_info.args.enable_http_apis, modules)
            except ValidationError as error:
                self.logger.error(error)
                return

            # Run HTTP Server if there are http enabled APIs
            if len(http_modules) > 0:
                enabled_module_names = tuple(mod.get_name() for mod in http_modules)
                self.logger.info("JSON-RPC modules exposed via HTTP: %s", enabled_module_names)
                non_http_modules = set(type(mod) for mod in modules) - set(http_modules)
                exec = rpc.execute_with_access_control(non_http_modules)
                http_server = HTTPServer(
                    host=boot_info.args.http_listen_address,
                    handler=RPCHandler.handle(exec),
                    port=boot_info.args.http_port,
                    service_name='JSONRPC'
                )
                services_to_exit += (http_server,)

            await run_background_asyncio_services(services_to_exit)
