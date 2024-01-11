import math

from eth_abi.utils.numeric import ceil32
from eth_utils import big_endian_to_int, encode_hex, keccak

from veda import precompiles, constants
from veda._utils.address import force_bytes_to_address
from veda._utils.numeric import get_highest_bit_index
from veda._utils.padding import zpad_right
from veda.abc import StateAPI, MessageAPI, TransactionContextAPI, ComputationAPI
from veda.constants import GAS_ECADD, GAS_ECMUL, GAS_ECPAIRING_BASE, GAS_ECPAIRING_PER_POINT, STACK_DEPTH_LIMIT
from veda.exceptions import OutOfGas, ReservedBytesInCode, VMError, StackDepthLimit, InsufficientFunds
from veda.precompiles import modexp
from veda.precompiles.modexp import extract_lengths
from veda.vm.forks.veda.constants import MAX_INITCODE_SIZE, INITCODE_WORD_COST
from veda.vm.forks.veda.opcodes import VEDA_OPCODES
from .constants import GAS_MOD_EXP_QUADRATIC_DENOMINATOR_EIP_2565
from ...computation import BaseComputation
from ...gas_meter import GasMeter, allow_negative_refund_strategy

EIP3541_RESERVED_STARTING_BYTE = b"\xef"
EIP170_CODE_SIZE_LIMIT = 24576

def _calculate_multiplication_complexity(base_length: int, modulus_length: int) -> int:
    max_length = max(base_length, modulus_length)
    words = math.ceil(max_length / 8)
    return words**2


def _calculate_iteration_count(
    exponent_length: int, first_32_exponent_bytes: bytes
) -> int:
    first_32_exponent = big_endian_to_int(first_32_exponent_bytes)

    highest_bit_index = get_highest_bit_index(first_32_exponent)

    if exponent_length <= 32:
        iteration_count = highest_bit_index
    else:
        iteration_count = highest_bit_index + (8 * (exponent_length - 32))

    return max(iteration_count, 1)

def _compute_modexp_gas_fee_eip_2565(data: bytes) -> int:
    base_length, exponent_length, modulus_length = extract_lengths(data)

    base_end_idx = 96 + base_length
    exponent_end_idx = base_end_idx + exponent_length

    first_32_exponent_bytes = zpad_right(
        data[base_end_idx:exponent_end_idx],
        to_size=min(exponent_length, 32),
    )[:32]
    iteration_count = _calculate_iteration_count(
        exponent_length,
        first_32_exponent_bytes,
    )

    multiplication_complexity = _calculate_multiplication_complexity(
        base_length, modulus_length
    )
    return max(
        200,
        multiplication_complexity
        * iteration_count
        // GAS_MOD_EXP_QUADRATIC_DENOMINATOR_EIP_2565,
    )

PRECOMPILES = {
    force_bytes_to_address(b"\x01"): precompiles.ecrecover,
    force_bytes_to_address(b"\x02"): precompiles.sha256,
    force_bytes_to_address(b"\x03"): precompiles.ripemd160,
    force_bytes_to_address(b"\x04"): precompiles.identity,
    force_bytes_to_address(b"\x05"): modexp(
        gas_calculator=_compute_modexp_gas_fee_eip_2565
    ),
    force_bytes_to_address(b"\x06"): precompiles.ecadd(gas_cost=GAS_ECADD),
    force_bytes_to_address(b"\x07"): precompiles.ecmul(gas_cost=GAS_ECMUL),
    force_bytes_to_address(b"\x08"): precompiles.ecpairing(
        gas_cost_base=GAS_ECPAIRING_BASE,
        gas_cost_per_point=GAS_ECPAIRING_PER_POINT,
    ),
    force_bytes_to_address(b"\x09"): precompiles.blake2b_fcompress,
}

class VedaComputation(BaseComputation):
    """
    A class for all execution *message* computations in the ``Shanghai`` hard fork
    """

    opcodes = VEDA_OPCODES
    _precompiles = PRECOMPILES

    def __init__(
        self,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI,
    ) -> None:
        super().__init__(state, message, transaction_context)

        # EIP-3651: Warm COINBASE
        # self.state.mark_address_warm(self.state.coinbase)

    @classmethod
    def validate_create_message(cls, message: MessageAPI) -> None:
        # EIP-3860: initcode size limit
        initcode_length = len(message.code)

        if initcode_length > MAX_INITCODE_SIZE:
            raise OutOfGas(
                "Contract code size exceeds EIP-3860 limit of "
                f"{MAX_INITCODE_SIZE}. Got code of size: {initcode_length}"
            )

    @classmethod
    def consume_initcode_gas_cost(cls, computation: ComputationAPI) -> None:
        # EIP-3860: initcode gas cost
        initcode_length = len(computation.msg.code)

        initcode_gas_cost = INITCODE_WORD_COST * ceil32(initcode_length) // 32
        computation.consume_gas(
            initcode_gas_cost,
            reason="EIP-3860 initcode cost",
        )

    @classmethod
    def validate_contract_code(cls, contract_code: bytes) -> None:
        if len(contract_code) > EIP170_CODE_SIZE_LIMIT:
            raise OutOfGas(
                f"Contract code size exceeds EIP170 limit of {EIP170_CODE_SIZE_LIMIT}."
                f"  Got code of size: {len(contract_code)}"
            )

        if contract_code[:1] == EIP3541_RESERVED_STARTING_BYTE:
            raise ReservedBytesInCode(
                "Contract code begins with EIP3541 reserved byte '0xEF'."
            )

    def _configure_gas_meter(self) -> GasMeter:
        return GasMeter(self.msg.gas, allow_negative_refund_strategy)



    @classmethod
    def apply_message(
        cls,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI,
    ) -> ComputationAPI:
        snapshot = state.snapshot()

        if message.depth > STACK_DEPTH_LIMIT:
            raise StackDepthLimit("Stack depth limit reached")

        # if message.should_transfer_value and message.value:
        #     sender_balance = state.get_balance(message.sender)
        #
        #     if sender_balance < message.value:
        #         raise InsufficientFunds(
        #             f"Insufficient funds: {sender_balance} < {message.value}"
        #         )
        #
        #     state.delta_balance(message.sender, -1 * message.value)
        #     state.delta_balance(message.storage_address, message.value)
        #
        #     cls.logger.debug2(
        #         "TRANSFERRED: %s from %s -> %s",
        #         message.value,
        #         encode_hex(message.sender),
        #         encode_hex(message.storage_address),
        #     )

        state.touch_account(message.storage_address)

        computation = cls.apply_computation(
            state,
            message,
            transaction_context,
        )

        if computation.is_error:
            state.revert(snapshot)
        else:
            state.commit(snapshot)

        return computation

    @classmethod
    def apply_create_message(
        cls,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI,
    ) -> ComputationAPI:
        snapshot = state.snapshot()

        # EIP161 nonce incrementation
        state.increment_nonce(message.storage_address)

        cls.validate_create_message(message)

        computation = cls.apply_message(state, message, transaction_context)

        if computation.is_error:
            state.revert(snapshot)
            return computation
        else:
            contract_code = computation.output

            if contract_code:
                try:
                    cls.validate_contract_code(contract_code)

                    contract_code_gas_cost = (
                        len(contract_code) * constants.GAS_CODEDEPOSIT
                    )
                    computation.consume_gas(
                        contract_code_gas_cost,
                        reason="Write contract code for CREATE",
                    )
                except VMError as err:
                    # Different from Frontier: reverts state on gas failure while
                    # writing contract code.
                    computation.error = err
                    state.revert(snapshot)
                    cls.logger.debug2(f"VMError setting contract code: {err}")
                else:
                    if cls.logger:
                        cls.logger.debug2(
                            "SETTING CODE: %s -> length: %s | hash: %s",
                            encode_hex(message.storage_address),
                            len(contract_code),
                            encode_hex(keccak(contract_code)),
                        )

                    state.set_code(message.storage_address, contract_code)
                    state.commit(snapshot)
            else:
                state.commit(snapshot)
            return computation


