from abc import abstractmethod
from typing import (
    Dict,
    Iterable,
    Sequence,
    Tuple,
    Type,
)

from eth_typing import Hash32

from veda.abc import (
    BlockAPI,
    BlockHeaderAPI,
    ReceiptAPI,
    ReceiptBuilderAPI,
    SignedTransactionAPI,
    TransactionBuilderAPI,
)
from veda.db.chain import ChainDB

from veda._utils.async_dispatch import async_method
from veda.db.async_headerdb import BaseAsyncHeaderDB


class BaseAsyncChainDB(BaseAsyncHeaderDB, ChainDB):
    """
    Abstract base class for the async counterpart to ``ChainDatabaseAPI``.
    """

    @abstractmethod
    async def coro_exists(self, key: bytes) -> bool:
        ...

    @abstractmethod
    async def coro_get(self, key: bytes) -> bytes:
        ...

    @abstractmethod
    async def coro_persist_block(
        self,
        block: BlockAPI,
    ) -> Tuple[Tuple[Hash32, ...], Tuple[Hash32, ...]]:
        ...

    @abstractmethod
    async def coro_persist_trie_data_dict(self, trie_data_dict: Dict[Hash32, bytes]) -> None:
        ...

    @abstractmethod
    async def coro_get_block_transactions(
            self,
            header: BlockHeaderAPI,
            transaction_class: Type[TransactionBuilderAPI]) -> Iterable[SignedTransactionAPI]:
        ...

    @abstractmethod
    async def coro_get_receipts(
        self,
        header: BlockHeaderAPI,
        receipt_class: Type[ReceiptBuilderAPI],
    ) -> Tuple[ReceiptAPI, ...]:
        ...


class AsyncChainDB(BaseAsyncChainDB):
    coro_exists = async_method(BaseAsyncChainDB.exists)
    coro_get = async_method(BaseAsyncChainDB.get)
    coro_get_block_header_by_hash = async_method(BaseAsyncChainDB.get_block_header_by_hash)
    coro_get_canonical_head = async_method(BaseAsyncChainDB.get_canonical_head)
    coro_get_score = async_method(BaseAsyncChainDB.get_score)
    coro_header_exists = async_method(BaseAsyncChainDB.header_exists)
    coro_get_canonical_block_hash = async_method(BaseAsyncChainDB.get_canonical_block_hash)
    coro_get_canonical_block_header_by_number = async_method(BaseAsyncChainDB.get_canonical_block_header_by_number)  # noqa: E501
    coro_persist_checkpoint_header = async_method(BaseAsyncChainDB.persist_checkpoint_header)
    coro_persist_header = async_method(BaseAsyncChainDB.persist_header)
    coro_persist_header_chain = async_method(BaseAsyncChainDB.persist_header_chain)
    coro_persist_block = async_method(BaseAsyncChainDB.persist_block)
    coro_persist_trie_data_dict = async_method(BaseAsyncChainDB.persist_trie_data_dict)
    coro_get_block_transactions = async_method(BaseAsyncChainDB.get_block_transactions)
    coro_get_receipts = async_method(BaseAsyncChainDB.get_receipts)
