from functools import (
    partial,
)
from typing import (
    Tuple, cast,
)

from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    Address, Hash32,
)
import rlp
from rlp.sedes import big_endian_int, binary

from veda._utils.transactions import (
    IntrinsicGasSchedule,
    calculate_intrinsic_gas,
)
from veda.abc import (
    ReceiptAPI,
    SignedTransactionAPI,
)
from veda.constants import (
    CREATE_CONTRACT_ADDRESS,
    GAS_TX,
    GAS_TXDATANONZERO,
    GAS_TXDATAZERO, GAS_TXCREATE,
)
from veda.rlp.logs import (
    Log,
)
from veda.rlp.receipts import (
    Receipt,
)
from veda.rlp.sedes import address, address_veda
from veda.rlp.transactions import (
    BaseTransaction,
)
from veda.validation import (
    validate_canonical_address,
    validate_gte,
    validate_is_bytes,
    validate_is_integer,
    validate_lt_secpk1n,
    validate_lte,
    validate_uint64,
    validate_uint256,
)

TX_GAS_SCHEDULE = IntrinsicGasSchedule(
    gas_tx=GAS_TX,
    gas_txcreate=GAS_TXCREATE,
    gas_txdatazero=GAS_TXDATAZERO,
    gas_txdatanonzero=GAS_TXDATANONZERO,
)



class VedaTransaction(BaseTransaction):

    def validate(self) -> None:
        validate_uint64(self.nonce, title="Transaction.nonce")
        validate_uint256(self.gas, title="Transaction.gas")
        if self.to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(self.to, title="Transaction.to")
        validate_is_bytes(self.data, title="Transaction.data")
        validate_canonical_address(self.veda_sender, title="Transaction.veda_sender")

        super().validate()

    def get_sender(self) -> Address:
        return self.veda_sender
        # return extract_transaction_sender(self)

    def get_intrinsic_gas(self) -> int:
        return calculate_intrinsic_gas(TX_GAS_SCHEDULE, self)

    @classmethod
    def new_transaction(
        cls,
        nonce: int,
        gas: int,
        to: Address,
        data: bytes,
        veda_sender: Address,
        veda_txhash: Hash32
    ) -> SignedTransactionAPI:
        return cls(nonce, gas, to, data, veda_sender, veda_txhash)

    def make_receipt(
        self,
        status: bytes,
        gas_used: int,
        log_entries: Tuple[Tuple[bytes, Tuple[int, ...], bytes], ...],
    ) -> ReceiptAPI:
        # 'status' is a misnomer in Frontier. Until Byzantium, it is the
        # intermediate state root.

        logs = [Log(address, topics, data) for address, topics, data in log_entries]

        return Receipt(
            state_root=status,
            gas_used=gas_used,
            logs=logs,
        )

