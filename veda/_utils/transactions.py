from typing import (
    NamedTuple,
)

from eth_keys import (
    datatypes,
    keys,
)
from eth_keys.exceptions import (
    BadSignature,
)
from eth_utils import (
    ValidationError,
    int_to_big_endian,
)
import rlp

from veda._utils.numeric import (
    is_even,
)
from veda.abc import (
    SignedTransactionAPI,
)
from veda.constants import (
    CREATE_CONTRACT_ADDRESS,
)
from veda.rlp.transactions import (
    BaseTransaction,
)
from veda.typing import (
    VRS,
    Address,
)

EIP155_CHAIN_ID_OFFSET = 35
# Add this offset to y_parity to get "v" for legacy transactions, from Frontier
V_OFFSET = 27


def is_eip_155_signed_transaction(transaction: BaseTransaction) -> bool:
    return transaction.v >= EIP155_CHAIN_ID_OFFSET


def extract_chain_id(v: int) -> int:
    if is_even(v):
        return (v - EIP155_CHAIN_ID_OFFSET - 1) // 2
    else:
        return (v - EIP155_CHAIN_ID_OFFSET) // 2

class IntrinsicGasSchedule(NamedTuple):
    gas_tx: int
    gas_txcreate: int
    gas_txdatazero: int
    gas_txdatanonzero: int


def calculate_intrinsic_gas(
    gas_schedule: IntrinsicGasSchedule,
    transaction: SignedTransactionAPI,
) -> int:
    num_zero_bytes = transaction.data.count(b"\x00")
    num_non_zero_bytes = len(transaction.data) - num_zero_bytes
    if transaction.to == CREATE_CONTRACT_ADDRESS:
        create_cost = gas_schedule.gas_txcreate
    else:
        create_cost = 0
    return (
        gas_schedule.gas_tx
        + num_zero_bytes * gas_schedule.gas_txdatazero
        + num_non_zero_bytes * gas_schedule.gas_txdatanonzero
        + create_cost
    )
