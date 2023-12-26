from typing import Generic, TypeVar

from lahja import EndpointAPI, BaseEvent

from veda.rpc.base import BaseRPCModule, AsyncChainAPI

TChain = TypeVar('TChain')

class ChainReplacementEvent(BaseEvent, Generic[TChain]):

    def __init__(self, chain: TChain):
        self.chain = chain


class ChainBasedRPCModule(BaseRPCModule, Generic[TChain]):

    def __init__(self, chain: TChain, event_bus: EndpointAPI) -> None:
        self.chain = chain
        self.event_bus = event_bus

        self.event_bus.subscribe(
            ChainReplacementEvent,
            lambda ev: self.on_chain_replacement(ev.chain)
        )

    def on_chain_replacement(self, chain: TChain) -> None:
        self.chain = chain

Eth1ChainRPCModule = ChainBasedRPCModule[AsyncChainAPI]
