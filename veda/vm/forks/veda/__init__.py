from typing import (
    Type, Iterable, Any,
)

from eth_bloom import BloomFilter
from eth_typing import Hash32

from veda.abc import BlockHeaderAPI, ReceiptAPI, SignedTransactionAPI, ComputationAPI, StateAPI, BlockAPI, \
    ExecutionContextAPI, ChainContextAPI
from veda.constants import BLOCK_REWARD, UNCLE_DEPTH_PENALTY_FACTOR, ZERO_HASH32
from veda.rlp.blocks import BaseBlock
from veda.rlp.logs import Log
from veda.rlp.receipts import Receipt
from veda.vm.state import BaseState

from .blocks import VedaBlock, VedaBlockHeader
from .constants import MAX_REFUND_QUOTIENT
from .headers import (
    configure_veda_header,
    create_veda_header_from_parent,
)
from .state import VedaState
from .validation import validate_veda_transaction_against_header
from veda.constants import EIP658_TRANSACTION_STATUS_CODE_FAILURE, EIP658_TRANSACTION_STATUS_CODE_SUCCESS
from veda.vm.base import VM
from .headers import compute_veda_difficulty
from veda.vm.execution_context import ExecutionContext


def make_veda_receipt(
    computation: ComputationAPI, new_cumulative_gas_used: int
) -> ReceiptAPI:
    # Reusable for other forks
    # This skips setting the state root (set to 0 instead). The logic for making a
    # state root lives in the FrontierVM, so that state merkelization at each receipt
    # is skipped at Byzantium+.

    logs = [
        Log(address, topics, data)
        for address, topics, data in computation.get_log_entries()
    ]

    receipt = Receipt(
        state_root=ZERO_HASH32,
        gas_used=new_cumulative_gas_used,
        logs=logs,
    )

    return receipt


class VedaVM(VM):
    # fork name
    fork = "veda"

    # classes
    block_class: Type[BaseBlock] = VedaBlock
    _state_class: Type[BaseState] = VedaState

    # Methods
    create_header_from_parent = staticmethod(  # type: ignore
        create_veda_header_from_parent()
    )
    configure_header = configure_veda_header

    compute_difficulty = staticmethod(compute_veda_difficulty)  # type: ignore
    validate_transaction_against_header = validate_veda_transaction_against_header


    def add_receipt_to_header(
        self, old_header: BlockHeaderAPI, receipt: ReceiptAPI
    ) -> BlockHeaderAPI:
        # Skip merkelizing the account data and persisting it to disk on every
        # transaction. Starting in Byzantium, this is no longer necessary,
        # because the state root isn't in the receipt anymore.
        return old_header.copy(
            bloom=int(BloomFilter(old_header.bloom) | receipt.bloom),
            state_root=self.state.make_state_root(),
        )

    # TODO: VEDA/ delete this
    @classmethod
    def calculate_net_gas_refund(cls, consumed_gas: int, gross_refund: int) -> int:
        max_refund = consumed_gas // MAX_REFUND_QUOTIENT
        return min(max_refund, gross_refund)

    @classmethod
    def finalize_gas_used(
        cls, transaction: SignedTransactionAPI, computation: ComputationAPI
    ) -> int:
        gas_remaining = computation.get_gas_remaining()
        consumed_gas = transaction.gas - gas_remaining

        gross_refund = computation.get_gas_refund()
        net_refund = cls.calculate_net_gas_refund(consumed_gas, gross_refund)

        return consumed_gas - net_refund

    @classmethod
    def make_receipt(
        cls,
        base_header: BlockHeaderAPI,
        transaction: SignedTransactionAPI,
        computation: ComputationAPI,
        state: StateAPI,
    ) -> ReceiptAPI:
        gas_used = base_header.gas_used + cls.finalize_gas_used(
            transaction, computation
        )

        if computation.is_error:
            status_code = EIP658_TRANSACTION_STATUS_CODE_FAILURE
        else:
            status_code = EIP658_TRANSACTION_STATUS_CODE_SUCCESS

        return transaction.make_receipt(
            status_code, gas_used, computation.get_log_entries()
        )

    @staticmethod
    def get_block_reward() -> int:
        return 0

    @classmethod
    def get_nephew_reward(cls) -> int:
        return 0

    def _assign_block_rewards(self, block: BlockAPI) -> None:
        # No block reward or uncles / uncle rewards in PoS
        pass

    @classmethod
    def create_execution_context(
        cls,
        header: BlockHeaderAPI,
        prev_hashes: Iterable[Hash32],
        chain_context: ChainContextAPI,
    ) -> ExecutionContextAPI:
        return ExecutionContext(
            # coinbase=fee_recipient,
            timestamp=header.timestamp,
            block_number=header.block_number,
            difficulty=header.difficulty,
            mix_hash=ZERO_HASH32,
            gas_limit=header.gas_limit,
            prev_hashes=prev_hashes,
            chain_id=chain_context.chain_id,
        )

    def pack_block(self, block: BlockAPI, *args: Any, **kwargs: Any) -> BlockAPI:
        provided_fields = set(kwargs.keys())
        known_fields = set(VedaBlockHeader._meta.field_names)
        unknown_fields = provided_fields.difference(known_fields)

        if unknown_fields:
            raise AttributeError(
                f"Unable to set the field(s) {', '.join(known_fields)} "
                "on the `BlockHeader` class. "
                f"Received the following unexpected fields: {', '.join(unknown_fields)}."  # noqa: E501
            )

        header: BlockHeaderAPI = block.header.copy(**kwargs)

        packed_block = block.copy(header=header)

        return packed_block