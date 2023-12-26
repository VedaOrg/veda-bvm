from typing import (
    Optional,
    Sequence,
    Tuple,
    cast,
)

from cached_property import (
    cached_property,
)
from eth_hash.auto import (
    keccak,
)
from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    ValidationError,
)
import rlp
from rlp.sedes import (
    big_endian_int,
    binary,
)

from veda.abc import (
    BaseTransactionAPI,
    ComputationAPI,
    SignedTransactionAPI,
    TransactionBuilderAPI,
    TransactionFieldsAPI,
)

from .sedes import (
    address, address_veda, hash32,
)


class BaseTransactionMethods(BaseTransactionAPI):
    def validate(self) -> None:
        pass

    @property
    def intrinsic_gas(self) -> int:
        return self.get_intrinsic_gas()

    def gas_used_by(self, computation: ComputationAPI) -> int:
        return self.get_intrinsic_gas() + computation.get_gas_used()

    @property
    def chain_id(self) -> Optional[int]:
        return None

    @property
    def access_list(self) -> Sequence[Tuple[Address, Sequence[int]]]:
        return []


BASE_TRANSACTION_FIELDS = [
    ("nonce", big_endian_int),
    ("gas", big_endian_int),
    ("to", address),
    ("data", binary),
    ('veda_sender', address),
    ('veda_txhash', hash32),
]


class BaseTransactionFields(rlp.Serializable, TransactionFieldsAPI):
    fields = BASE_TRANSACTION_FIELDS

    @property
    def hash(self) -> Hash32:
        # TODO: VEDA/ Using txhash from verifier (verifier assure that txHash is unique)
        return self.veda_txhash


class SignedTransactionMethods(BaseTransactionMethods, SignedTransactionAPI):
    type_id: Optional[int] = None

    @cached_property
    def sender(self) -> Address:
        return self.get_sender()

    #
    # Validation
    #
    def validate(self) -> None:
        if self.gas < self.intrinsic_gas:
            raise ValidationError("Insufficient gas")
        # self.check_signature_validity()

    #
    # Signature and Sender
    #


class BaseTransaction(
    BaseTransactionFields,
    SignedTransactionMethods,
    TransactionBuilderAPI,
):
    # "Legacy" transactions implemented by BaseTransaction are a combination of
    # the transaction codec (TransactionBuilderAPI) *and* the transaction
    # object (SignedTransactionAPI). In a multi-transaction-type world, that
    # becomes less desirable, and that responsibility splits up. See Berlin
    # transactions, for example.

    # Note that it includes at least one legacy field (v) that is not
    # explicitly accessible in new transaction types. See the v docstring in
    # LegacyTransactionFieldsAPI for more.

    # this is duplicated to make the rlp library happy, otherwise it complains
    # about no fields being defined but inheriting from multiple `Serializable`
    # bases.
    fields = BASE_TRANSACTION_FIELDS

    @classmethod
    def decode(cls, encoded: bytes) -> SignedTransactionAPI:
        return rlp.decode(encoded, sedes=cls)

    def encode(self) -> bytes:
        return rlp.encode(self)

