from lahja import EndpointAPI

from veda.constants import TO_NETWORKING_BROADCAST_CONFIG
from veda.rpc.modules import BaseRPCModule


class Net(BaseRPCModule):

    def __init__(self, event_bus: EndpointAPI):
        self.event_bus = event_bus

    async def version(self) -> str:
        """
        Returns the current network ID.
        """
        return "1"

    async def peerCount(self) -> str:
        """
        Return the number of peers that are currently connected to the node
        """
        return hex(0)

    async def listening(self) -> bool:
        """
        Return `True` if the client is actively listening for network connections
        """
        return True
