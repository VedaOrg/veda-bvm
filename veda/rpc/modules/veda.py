import asyncio
from typing import Dict

from eth_typing import Address
from eth_utils import decode_hex, ExtendedDebugLogger, get_logger
from lahja import EndpointAPI, BroadcastConfig

from veda import constants
from veda.config import VedaConfig
from veda.constants import VEDA_EVENTBUS_ENDPOINT, TO_VEDA_BROADCAST_CONFIG
from veda.rpc.exceptions import RpcError
from veda.rpc.modules import BaseRPCModule
from veda.rpc.format import format_params, to_int_if_hex


class Veda(BaseRPCModule):

    logger: ExtendedDebugLogger = get_logger('veda.rpc.Veda')

    def __init__(self, event_bus: EndpointAPI, veda_config: VedaConfig) -> None:
        self.event_bus = event_bus
        self.veda_config = veda_config


    async def getHeartBeat(self) -> str:
        """
        Returns the current network ID.
        """
        return "OK"
    #
    # @format_params(decode_hex)
    # async def getVRC20Balances(self, address: Address) -> Dict[Address, str]:
    #     """
    #     Returns the current network ID.
    #     """
    #
    #     try:
    #         response = await asyncio.wait_for(
    #             self.event_bus.request(
    #                 QueryBalanceForAccount(address=address),
    #                 BroadcastConfig(filter_endpoint='vrc20_tracer')
    #             ),
    #             timeout=3,
    #         )
    #     except asyncio.TimeoutError as exc:
    #         raise RpcError(
    #             f"getVRC20Balances request timed out")
    #     #
    #     # response = await self.event_bus.request(
    #     #     QueryBalanceForAccount(address=address),
    #     #     TO_VEDA_BROADCAST_CONFIG
    #     # )
    #
    #     result = response.balances
    #     return result
