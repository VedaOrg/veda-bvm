from eth_typing import Address

from veda import constants
from veda._utils.address import force_bytes_to_address
from veda._utils.numeric import ceil32
from veda.abc import ComputationAPI
from veda.exceptions import WriteProtection
from veda.vm import mnemonics
from veda.vm.logic.context import push_balance_of_address, extcodecopy_execute, consume_extcodecopy_word_cost
from . import constants as veda_constants
from veda.vm.logic.storage import NetSStoreGasSchedule
from veda.vm.logic.system import Create as CreateEth, Create2 as Create2Eth, CreateOpcodeStackData, \
    selfdestruct_eip161_on_address
from .constants import (
    INITCODE_WORD_COST
)
from veda.vm.logic.call import DelegateCallEIP150, StaticCall, CallCodeEIP150, CallEIP161, CallParams


def _account_load_cost(was_cold: bool) -> int:
    if was_cold:
        return veda_constants.COLD_ACCOUNT_ACCESS_COST
    else:
        return veda_constants.WARM_STORAGE_READ_COST


def _mark_storage_warm(computation: ComputationAPI, slot: int) -> bool:
    """
    :return was_cold: True if the storage slot was not previously accessed
        during this transaction
    """
    storage_address = computation.msg.storage_address
    if computation.state.is_storage_warm(storage_address, slot):
        return False
    else:
        computation.state.mark_storage_warm(storage_address, slot)
        return True


def _mark_address_warm(computation: ComputationAPI, address: Address) -> bool:
    """
    Mark the given address as warm if it was not previously.

    :return was_cold: True if the account was not previously accessed
        during this transaction
    """

    if computation.state.is_address_warm(address):
        return False
    else:
        computation.state.mark_address_warm(address)
        return True


def _consume_gas_for_account_load(
    computation: ComputationAPI, address: Address, reason: str
) -> None:
    was_cold = _mark_address_warm(computation, address)
    gas_cost = _account_load_cost(was_cold)
    computation.consume_gas(gas_cost, reason=reason)


def balance_eip2929(computation: ComputationAPI) -> None:
    address = force_bytes_to_address(computation.stack_pop1_bytes())
    _consume_gas_for_account_load(computation, address, mnemonics.BALANCE)
    push_balance_of_address(address, computation)


def extcodesize_eip2929(computation: ComputationAPI) -> None:
    address = force_bytes_to_address(computation.stack_pop1_bytes())
    _consume_gas_for_account_load(computation, address, mnemonics.EXTCODEHASH)

    code_size = len(computation.state.get_code(address))
    computation.stack_push_int(code_size)


def extcodecopy_eip2929(computation: ComputationAPI) -> None:
    address, size = extcodecopy_execute(computation)
    consume_extcodecopy_word_cost(computation, size)
    _consume_gas_for_account_load(computation, address, mnemonics.EXTCODECOPY)


def extcodehash_eip2929(computation: ComputationAPI) -> None:
    """
    Return the code hash for a given address.
    EIP: https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1052.md
    """
    address = force_bytes_to_address(computation.stack_pop1_bytes())
    state = computation.state

    _consume_gas_for_account_load(computation, address, mnemonics.EXTCODEHASH)

    if state.account_is_empty(address):
        computation.stack_push_bytes(constants.NULL_BYTE)
    else:
        computation.stack_push_bytes(state.get_code_hash(address))


def sload_eip2929(computation: ComputationAPI) -> None:
    slot = computation.stack_pop1_int()

    if _mark_storage_warm(computation, slot):
        gas_cost = veda_constants.COLD_SLOAD_COST
    else:
        gas_cost = veda_constants.WARM_STORAGE_READ_COST
    computation.consume_gas(gas_cost, reason=mnemonics.SLOAD)

    value = computation.state.get_storage(
        address=computation.msg.storage_address,
        slot=slot,
    )
    computation.stack_push_int(value)


class Create(CreateEth):
    def max_child_gas_modifier(self, gas: int) -> int:
        return gas - (gas // 64)

    def get_gas_cost(self, data: CreateOpcodeStackData) -> int:
        eip2929_gas_cost = super().get_gas_cost(data)
        eip3860_gas_cost = INITCODE_WORD_COST * ceil32(data.memory_length) // 32
        return eip2929_gas_cost + eip3860_gas_cost
    def generate_contract_address(
        self,
        stack_data: CreateOpcodeStackData,
        call_data: bytes,
        computation: ComputationAPI,
    ) -> Address:
        address = super().generate_contract_address(stack_data, call_data, computation)
        computation.state.mark_address_warm(address)
        return address


class Create2(Create2Eth):
    def get_gas_cost(self, data: CreateOpcodeStackData) -> int:
        eip2929_gas_cost = super().get_gas_cost(data)
        eip3860_gas_cost = INITCODE_WORD_COST * ceil32(data.memory_length) // 32
        return eip2929_gas_cost + eip3860_gas_cost

    def generate_contract_address(
        self,
        stack_data: CreateOpcodeStackData,
        call_data: bytes,
        computation: ComputationAPI,
    ) -> Address:
        address = super().generate_contract_address(stack_data, call_data, computation)
        computation.state.mark_address_warm(address)
        return address

    def __call__(self, computation: ComputationAPI) -> None:
        if computation.msg.is_static:
            raise WriteProtection(
                "Cannot modify state while inside of a STATICCALL context"
            )
        return super().__call__(computation)


def selfdestruct(computation: ComputationAPI) -> None:
    beneficiary = force_bytes_to_address(computation.stack_pop1_bytes())

    if _mark_address_warm(computation, beneficiary):
        gas_cost = veda_constants.COLD_ACCOUNT_ACCESS_COST
        computation.consume_gas(
            gas_cost,
            reason=f"Implicit account load during {mnemonics.SELFDESTRUCT}",
        )

    selfdestruct_eip161_on_address(computation, beneficiary)


class LoadFeeByCacheWarmth:
    def get_account_load_fee(
        self,
        computation: ComputationAPI,
        code_address: Address,
    ) -> int:
        was_cold = _mark_address_warm(computation, code_address)
        return _account_load_cost(was_cold)


class CallVeda(LoadFeeByCacheWarmth, CallEIP161):
    def get_call_params(self, computation: ComputationAPI) -> CallParams:
        gas = computation.stack_pop1_int()
        to = force_bytes_to_address(computation.stack_pop1_bytes())

        (
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack_pop_ints(4)

        return (
            gas,
            0,  # value
            to,
            None,  # sender
            None,  # code_address
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
            False,  # should_transfer_value,
            True,  # is_static
        )

class DelegateCallVeda(LoadFeeByCacheWarmth, DelegateCallEIP150):
    pass


class StaticCallVeda(LoadFeeByCacheWarmth, StaticCall):
    pass


class CallCodeVeda(LoadFeeByCacheWarmth, CallCodeEIP150):
    pass
