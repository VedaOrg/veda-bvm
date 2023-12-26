from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
from typing import (
    Tuple,
)

from async_service import Service
from lahja import EndpointAPI

from veda._utils.services import run_background_asyncio_services

from veda.boot_info import BootInfo
from veda.config import (
    VedaAppConfig,
)
from veda.extensibility import AsyncioIsolatedComponent
from veda.http.handlers.rpc_handler import RPCHandler
from veda.http.server import HTTPServer
from veda.rpc.ipc import IPCServer
from veda.services.components.json_rpc.component import chain_for_config
from veda.services.components.syncer.internal_rpc import InternalRPCServer


class SyncerComponent(AsyncioIsolatedComponent):
    name = "Sync HTTP Service"

    endpoint_name = 'syncer'

    @property
    def is_enabled(self) -> bool:
        return True

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--disable-internal-rpc",
            action="store_true",
            help="Disables the JSON-RPC server",
        )
        arg_parser.add_argument(
            "--internal-rpc-http-listen-address",
            type=str,
            help="Address for the HTTP server to listen on",
            default="127.0.0.1",
        )
        arg_parser.add_argument(
            "--internal-rpc-http-port",
            type=int,
            help="Veda internal sync server port",
            default=8679,
        )
        arg_parser.add_argument(
            "--enable-internal-rpc-debug-mode",
            action='store_true',
            help="Enable server side debug mode",
            # default=False,
        )

    @classmethod
    def validate_cli(cls, boot_info: BootInfo) -> None:
        # this will trigger a ValidationError if the specified strategy isn't known.
        # cls.get_active_strategy(boot_info)

        # This will trigger a ValidationError if the loaded EIP1085 file
        # has errors such as an unsupported mining method
        boot_info.veda_config.get_app_config(VedaAppConfig).get_chain_config()

    async def do_run(self, event_bus: EndpointAPI) -> None:
        boot_info = self._boot_info
        veda_config = boot_info.veda_config


        with chain_for_config(veda_config, event_bus) as chain:
            rpc = InternalRPCServer(chain, event_bus, debug_mode=boot_info.args.enable_internal_rpc_debug_mode)

            # Run IPC Server
            ipc_server = IPCServer(rpc, boot_info.veda_config.internal_jsonrpc_ipc_path)
            services_to_exit: Tuple[Service, ...] = (
                ipc_server,
            )

            self.logger.info("Internal RPC Server exposed via HTTP: %s:%s",
                             boot_info.args.internal_rpc_http_listen_address, boot_info.args.internal_rpc_http_port)

            http_server = HTTPServer(
                host=boot_info.args.internal_rpc_http_listen_address,
                handler=RPCHandler.handle(rpc.execute),
                port=boot_info.args.internal_rpc_http_port,
                service_name='Syncer'
            )
            services_to_exit += (http_server,)

            await run_background_asyncio_services(services_to_exit)

if __name__ == "__main__":
    # SyncerComponent depends on a separate component to get peer candidates, so when running it
    # you must pass the path to the discovery component's IPC file, like:
    # $ python .../syncer/component.py --veda-root-dir /tmp/syncer \
    #        --connect-to-endpoints /tmp/syncer/mainnet/ipcs-veda/discovery.ipc
    from veda.extensibility.component import run_asyncio_veda_component
    run_asyncio_veda_component(SyncerComponent)