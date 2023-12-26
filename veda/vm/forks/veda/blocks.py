from abc import ABC
from typing import (
    Sequence,
    Tuple,
    Type, cast, Optional,
)

import rlp
from eth_bloom import (
    BloomFilter,
)
from eth_typing import (
    BlockNumber,
    Hash32, Address,
)
from eth_utils import encode_hex, keccak
from rlp.sedes import (
    CountableList, big_endian_int, binary,
)
from trie.exceptions import (
    MissingTrieNode,
)

from veda._utils.headers import new_timestamp_from_parent
from veda.abc import (
    BlockHeaderAPI,
    ChainDatabaseAPI,
    ReceiptAPI,
    ReceiptBuilderAPI,
    SignedTransactionAPI,
    TransactionBuilderAPI, VedaBlockHeaderAPI,
)
from veda.constants import ZERO_ADDRESS, ZERO_HASH32, EMPTY_UNCLE_HASH, BLANK_ROOT_HASH, GENESIS_NONCE, \
    GENESIS_PARENT_HASH, GENESIS_BLOCK_NUMBER
from veda.exceptions import (
    BlockNotFound,
    HeaderNotFound,
)
from veda.rlp.blocks import (
    BaseBlock,
)
from veda.rlp.headers import (
    BlockHeader,
)
from veda.rlp.receipts import (
    Receipt,
)
from veda.rlp.sedes import hash32, trie_root, address, uint256

from .transactions import (
    VedaTransaction,
)


class VedaBlockHeader(rlp.Serializable, BlockHeaderAPI, ABC):
    fields = [
        ("parent_hash", hash32),
        # ("uncles_hash", hash32),
        ("coinbase", address),
        ("state_root", trie_root),
        ("transaction_root", trie_root),
        ("receipt_root", trie_root),
        ("bloom", uint256),
        ("difficulty", big_endian_int),
        ("block_number", big_endian_int),
        ("gas_limit", big_endian_int),
        ("gas_used", big_endian_int),
        ("timestamp", big_endian_int),
        ("extra_data", binary),
        ("mix_hash", binary),
        # ("base_fee_per_gas", big_endian_int),
        ("veda_block_hash", hash32),
        ("veda_block_number", big_endian_int),
        ("veda_timestamp", big_endian_int),
    ]

    def __init__(
        self,
        difficulty: int,
        block_number: BlockNumber,
        gas_limit: int,
        timestamp: int = None,
        coinbase: Address = ZERO_ADDRESS,
        parent_hash: Hash32 = ZERO_HASH32,
        state_root: Hash32 = BLANK_ROOT_HASH,
        transaction_root: Hash32 = BLANK_ROOT_HASH,
        receipt_root: Hash32 = BLANK_ROOT_HASH,
        bloom: int = 0,
        gas_used: int = 0,
        extra_data: bytes = b"",
        mix_hash: Hash32 = ZERO_HASH32,
        # nonce: bytes = GENESIS_NONCE,
        veda_block_hash: Hash32 = ZERO_HASH32,
        veda_block_number: BlockNumber = 0,
        veda_timestamp: int = 0,
    ) -> None:
        if timestamp is None:
            if parent_hash == ZERO_HASH32:
                timestamp = new_timestamp_from_parent(None)
            else:
                # without access to the parent header, we cannot select a new
                # timestamp correctly
                raise ValueError(
                    "Must set timestamp explicitly if this is not a genesis header"
                )

        super().__init__(
            parent_hash=parent_hash,
            coinbase=coinbase,
            state_root=state_root,
            transaction_root=transaction_root,
            receipt_root=receipt_root,
            bloom=bloom,
            difficulty=difficulty,
            block_number=block_number,
            gas_limit=gas_limit,
            gas_used=gas_used,
            timestamp=timestamp,
            extra_data=extra_data,
            mix_hash=mix_hash,
            # nonce=nonce,
            veda_block_hash=veda_block_hash,
            veda_block_number=veda_block_number,
            veda_timestamp=veda_timestamp,
        )

    def __str__(self) -> str:
        return (
            f"<VedaBlockHeader "
            f"#{self.block_number} {encode_hex(self.hash)[2:10]}>"
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            # Use veda block hash instead of keccak(rlp.encode(self))
            self._hash = self.veda_block_hash
        return cast(Hash32, self._hash)
    @property
    def mining_hash(self) -> Hash32:
        # dummy hash
        return ZERO_HASH32

    @property
    def hex_hash(self) -> str:
        return encode_hex(self.hash)

    @property
    def is_genesis(self) -> bool:
        return self.parent_hash == GENESIS_PARENT_HASH and self.block_number == GENESIS_BLOCK_NUMBER



class VedaBlock(BaseBlock):
    transaction_builder = VedaTransaction
    receipt_builder = Receipt

    fields = [
        ("header", VedaBlockHeader),
        # ("veda_header", VedaBlockHeader),
        ("transactions", CountableList(transaction_builder)),
        # ("uncles", CountableList(VedaBlockHeader, max_length=0)),
    ]


    bloom_filter = None

    def __init__(
        self,
        header: BlockHeaderAPI,
        transactions: Sequence[SignedTransactionAPI] = None,
    ) -> None:
        if transactions is None:
            transactions = []

        self.bloom_filter = BloomFilter(header.bloom)

        super().__init__(
            header=header,
            transactions=transactions,
        )

    #
    # Helpers
    #
    @property
    def number(self) -> BlockNumber:
        return self.header.block_number

    @property
    def hash(self) -> Hash32:
        return self.header.hash

    @property
    def veda_block_hash(self) -> Hash32:
        return self.header.block_hash

    @property
    def veda_block_number(self) -> BlockNumber:
        return self.header.block_number

    @property
    def veda_timestamp(self) -> int:
        return self.header.veda_timestamp

    #
    # Transaction class for this block class
    #
    @classmethod
    def get_transaction_builder(cls) -> Type[TransactionBuilderAPI]:
        return cls.transaction_builder

    @classmethod
    def get_receipt_builder(cls) -> Type[ReceiptBuilderAPI]:
        return cls.receipt_builder

    #
    # Receipts API
    #
    def get_receipts(self, chaindb: ChainDatabaseAPI) -> Tuple[ReceiptAPI, ...]:
        return chaindb.get_receipts(self.header, self.get_receipt_builder())

    #
    # Header API
    #
    @classmethod
    def from_header(
        cls, header: BlockHeaderAPI, chaindb: ChainDatabaseAPI
    ) -> "VedaBlock":
        """
        Returns the block denoted by the given block header.

        :raise veda.exceptions.BlockNotFound: if transactions or uncle headers missing
        """

        try:
            transactions = chaindb.get_block_transactions(
                header, cls.get_transaction_builder()
            )
        except MissingTrieNode as exc:
            raise BlockNotFound(
                f"Transactions not found in database for {header}: {exc}"
            ) from exc

        return cls(
            header=header,
            transactions=transactions,
        )

