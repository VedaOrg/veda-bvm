from typing import Iterable

from lahja import EndpointAPI

from eth_utils import (
    to_tuple,
)

from veda.rpc.base import AsyncChainAPI, BaseRPCModule
from veda.config import VedaConfig


@to_tuple
def initialize_veda_modules(chain: AsyncChainAPI,
                            event_bus: EndpointAPI,
                            veda_config: VedaConfig) -> Iterable[BaseRPCModule]:
    from .eth import Eth  # noqa: F401
    from .veda import Veda

    yield Eth(chain, event_bus, veda_config)
    yield Veda(event_bus, veda_config)
