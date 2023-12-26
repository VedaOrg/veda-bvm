from eth_utils import (
    ValidationError,
)

from veda.abc import (
    BlockHeaderAPI,
    SignedTransactionAPI,
    StateAPI,
    VirtualMachineAPI,
)


def validate_veda_transaction(
    state: StateAPI, transaction: SignedTransactionAPI
) -> None:
    # base_fee_per_gas = state.execution_context.base_fee_per_gas
    # if transaction.max_fee_per_gas < base_fee_per_gas:
    #     raise ValidationError(
    #         f"Sender's max fee per gas ({transaction.max_fee_per_gas}) is "
    #         f"lower than block's base fee per gas ({base_fee_per_gas})"
    #     )

    sender_nonce = state.get_nonce(transaction.sender)

    if sender_nonce != transaction.nonce:
        raise ValidationError(
            f"Invalid transaction nonce: Expected {sender_nonce}, "
            f"but got {transaction.nonce}"
        )


def validate_veda_transaction_against_header(
    _vm: VirtualMachineAPI,
    base_header: BlockHeaderAPI,
    transaction: SignedTransactionAPI,
) -> None:
    # TODO: VEDA/ ignore block gas limit ?
    # if base_header.gas_used + transaction.gas > base_header.gas_limit:
    #     raise ValidationError(
    #         f"Transaction exceeds gas limit: using {transaction.gas}, "
    #         f"bringing total to {base_header.gas_used + transaction.gas}, "
    #         f"but limit is {base_header.gas_limit}"
    #     )
    return
