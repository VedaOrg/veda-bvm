import uuid
from abc import abstractmethod, ABC
from typing import Tuple, Hashable

from eth_typing import BlockNumber, Hash32

from veda.abc import (
    BlockAPI,
    ChainAPI,
    BlockHeaderAPI,
    BlockImportResult,
    ReceiptAPI,
    SignedTransactionAPI,
)


# This class is a work in progress; its main purpose is to define the API of an asyncio-compatible
# Chain implementation.
class AsyncChainAPI(ChainAPI):
    @abstractmethod
    async def coro_import_block(self,
                                block: BlockAPI,
                                perform_validation: bool = True,
                                ) -> BlockImportResult:
        ...

    @abstractmethod
    async def coro_validate_chain(
            self,
            parent: BlockHeaderAPI,
            chain: Tuple[BlockHeaderAPI, ...],
            seal_check_random_sample_rate: int = 1) -> None:
        ...

    @abstractmethod
    async def coro_validate_receipt(self,
                                    receipt: ReceiptAPI,
                                    at_header: BlockHeaderAPI) -> None:
        ...

    @abstractmethod
    async def coro_get_ancestors(self, limit: int, header: BlockHeaderAPI) -> Tuple[BlockAPI, ...]:
        ...

    @abstractmethod
    async def coro_get_block_by_hash(self,
                                     block_hash: Hash32) -> BlockAPI:
        ...

    @abstractmethod
    async def coro_get_block_by_header(self,
                                       header: BlockHeaderAPI) -> BlockAPI:
        ...

    @abstractmethod
    async def coro_get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeaderAPI:
        ...

    @abstractmethod
    async def coro_get_canonical_block_by_number(self,
                                                 block_number: BlockNumber) -> BlockAPI:
        ...

    @abstractmethod
    async def coro_get_canonical_head(self) -> BlockHeaderAPI:
        ...

    @abstractmethod
    async def coro_get_canonical_block_header_by_number(
            self,
            block_number: BlockNumber) -> BlockHeaderAPI:
        ...

    @abstractmethod
    async def coro_get_score(self, block_hash: Hash32) -> int:
        ...

    @abstractmethod
    async def coro_get_canonical_transaction_index(
            self,
            transaction_hash: Hash32) -> Tuple[BlockNumber, int]:
        ...

    @abstractmethod
    async def coro_get_canonical_transaction(self,
                                             transaction_hash: Hash32) -> SignedTransactionAPI:
        ...

    @abstractmethod
    async def coro_get_canonical_transaction_by_index(
            self,
            block_number: BlockNumber,
            index: int) -> SignedTransactionAPI:
        ...

    @abstractmethod
    async def coro_get_transaction_receipt(self, transaction_hash: Hash32) -> ReceiptAPI:
        ...

    @abstractmethod
    async def coro_get_transaction_receipt_by_index(self,
                                                    block_number: BlockNumber,
                                                    index: int) -> ReceiptAPI:
        ...



class BaseRPCModule(ABC):

    @classmethod
    def get_name(cls) -> str:
        # By default the name is the lower-case class name.
        # This encourages a standard name of the module, but can
        # be overridden if necessary.
        return cls.__name__.lower()

class NodeAPI(ABC):
    ...

class SessionAPI(ABC, Hashable):
    id: uuid.UUID
    remote: NodeAPI