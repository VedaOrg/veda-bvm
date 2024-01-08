from typing import Dict, List
from eth_utils import ExtendedDebugLogger, get_logger
from lahja import EndpointAPI
from veda.config import VedaConfig
from veda.rpc.modules import BaseRPCModule


class TxPool(BaseRPCModule):
    '''
    Veda doesn't have a txpool, so we just return empty lists.
    '''

    logger: ExtendedDebugLogger = get_logger('veda.rpc.Txpool')

    def __init__(self, event_bus: EndpointAPI, veda_config: VedaConfig) -> None:
        self.event_bus = event_bus
        self.veda_config = veda_config

    async def content(self) -> List:
        return []

    async def inspect(self) -> List:
        return []

    async def status(self) -> Dict:
        return {
            'pending': [],
            'queued': []
        }

    async def contentFrom(self, address: str) -> List:
        return []

