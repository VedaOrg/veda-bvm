import time
from typing import (
    Any,
    Dict,
    Tuple,
    Type, Optional, Union, Sequence,
)

from veda.abc import (
    AtomicDatabaseAPI,
    BlockAndMetaWitness,
    BlockAPI,
    BlockHeaderAPI,
    BlockImportResult,
    ComputationAPI,
    ReceiptAPI,
    SignedTransactionAPI,
)

from eth_typing import BlockNumber
from eth_utils import decode_hex

from veda.abc import VirtualMachineAPI
from veda.chains.base import Chain
from .constants import VEDA_CHAIN_ID
from veda.rlp.headers import BlockHeader
from veda.vm.forks import (
    VedaVM
)
from veda import constants


VEDA_VM_CONFIGURATION = (
    # Note: Frontier and Homestead are excluded since this chain
    # starts at Tangerine Whistle.
    (BlockNumber(0), VedaVM),
)


class BaseVedaChain:
    vm_configuration: Tuple[
        Tuple[BlockNumber, Type[VirtualMachineAPI]], ...
    ] = VEDA_VM_CONFIGURATION
    chain_id: int = VEDA_CHAIN_ID


VEDA_GENESIS_HEADER = BlockHeader(
    block_number=0,
    bloom=0,
    # coinbase=constants.ZERO_ADDRESS,
    difficulty=1,
    gas_limit=10485760,
    gas_used=0,
    mix_hash=constants.ZERO_HASH32,
    nonce=decode_hex("0x0000000000000000"),
    parent_hash=constants.GENESIS_PARENT_HASH,
    receipt_root=constants.BLANK_ROOT_HASH,
    state_root=decode_hex(
        "0x5d6cded585e73c4e322c30c2f782a336316f17dd85a4863b9d838d2d4b8b3008"
    ),
    timestamp=1700984871,
    transaction_root=constants.BLANK_ROOT_HASH,
    # uncles_hash=constants.EMPTY_UNCLE_HASH,
)

class VedaChain(BaseVedaChain, Chain):
    header: BlockHeaderAPI = None

    def __init__(
        self, base_db: AtomicDatabaseAPI, header: BlockHeaderAPI = None
    ) -> None:
        super().__init__(base_db)
        self.header = self.ensure_header(header)

    def import_block(
        self, block: BlockAPI, perform_validation: bool = True
    ) -> BlockImportResult:
        result = super().import_block(block, perform_validation)

        self.header = self.ensure_header()
        return result

    def apply_transactions(self, transactions: Tuple[SignedTransactionAPI, ...]) -> Tuple[BlockAPI, Tuple[ReceiptAPI, ...], Tuple[ComputationAPI, ...]]:
        vm = self.get_vm(self.header)
        base_block = vm.get_block()

        header_with_receipt, applied_transactions, _receipts, _computations = vm.apply_all_transactions(transactions=transactions,
                                                                          base_header=base_block.header)

        vm.state.persist()

        new_header: BlockHeaderAPI = header_with_receipt.copy(
            state_root=vm.state.state_root
        )
        new_block = vm.set_block_transactions(vm.get_block(), new_header, applied_transactions, _receipts)

        self.header = new_block.header

        return new_block, _receipts, _computations

    def apply_transaction(
        self,
        transaction: Union[SignedTransactionAPI],
        env: Optional[Dict[str, Any]] = None
    ) -> Tuple[BlockAPI, ReceiptAPI, ComputationAPI]:
        vm = self.get_vm(self.header)
        base_block = vm.get_block()
        receipt, computation = vm.apply_transaction(base_block.header, transaction)

        header_with_receipt = vm.add_receipt_to_header(base_block.header, receipt)

        # since we are building the block locally,
        # we have to persist all the incremental state
        vm.state.persist()
        new_header: BlockHeaderAPI = header_with_receipt.copy(
            state_root=vm.state.state_root
        )

        transactions = base_block.transactions + (transaction,)
        receipts = base_block.get_receipts(self.chaindb) + (receipt,)

        new_block = vm.set_block_transactions(base_block, new_header, transactions, receipts)

        self.header = new_block.header

        return new_block, receipt, computation

    def set_header_timestamp(self, timestamp: int) -> None:
        self.header = self.header.copy(timestamp=timestamp)

    @staticmethod
    def _custom_header(base_header: BlockHeaderAPI, **kwargs: Any) -> BlockHeaderAPI:
        # header_fields = {"coinbase"}
        header_fields = {}
        header_params = {k: v for k, v in kwargs.items() if k in header_fields}
        return base_header.copy(**header_params)

    def mine_block(self, *args: Any, **kwargs: Any) -> BlockAPI:
        """
        Mine whatever transactions have been incrementally applied so far.
        """
        return self.mine_block_extended(*args, **kwargs).block

    def mine_block_extended(self, *args: Any, **kwargs: Any) -> BlockAndMetaWitness:
        custom_header = self._custom_header(self.header, **kwargs)
        vm = self.get_vm(custom_header)
        current_block = vm.get_block()
        mine_result = vm.mine_block(current_block, *args, **kwargs)
        mined_block = mine_result.block

        self.validate_block(mined_block)

        self.chaindb.persist_block(mined_block)
        self.header = self.create_header_from_parent(mined_block.header)
        return mine_result

    def get_vm(self, at_header: BlockHeaderAPI = None) -> VirtualMachineAPI:
        if at_header is None:
            at_header = self.header

        return super().get_vm(at_header)

