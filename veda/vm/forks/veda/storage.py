from eth_utils.toolz import (
    partial,
)

from veda.abc import ComputationAPI
from veda.exceptions import OutOfGas
from . import constants as veda_constants
from veda.vm.logic.storage import NetSStoreGasSchedule, net_sstore
from eth_utils.toolz import (
    curry,
)

from ... import mnemonics

GAS_SCHEDULE_EIP1283 = NetSStoreGasSchedule(
    sload_gas=200,
    sstore_set_gas=20000,
    sstore_reset_gas=5000,
    sstore_clears_schedule=15000,
)

GAS_SLOAD_EIP1884 = 800

GAS_SCHEDULE_EIP2200 = GAS_SCHEDULE_EIP1283._replace(
    sload_gas=GAS_SLOAD_EIP1884,
)


@curry
def sstore_eip2200_generic(
        gas_schedule: NetSStoreGasSchedule,
        computation: ComputationAPI,
) -> int:
    gas_remaining = computation.get_gas_remaining()
    if gas_remaining <= 2300:
        raise OutOfGas(
            "Net-metered SSTORE always fails below 2300 gas, per EIP-2200",
            gas_remaining,
        )
    else:
        return net_sstore(gas_schedule, computation)


sstore_eip2200 = sstore_eip2200_generic(GAS_SCHEDULE_EIP2200)


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


@curry
def sstore_eip2929_generic(
        gas_schedule: NetSStoreGasSchedule,
        computation: ComputationAPI,
) -> int:
    slot = sstore_eip2200_generic(gas_schedule, computation)

    if _mark_storage_warm(computation, slot):
        gas_cost = veda_constants.COLD_SLOAD_COST
        computation.consume_gas(
            gas_cost, reason=f"Implicit SLOAD during {mnemonics.SSTORE}"
        )

    return slot

GAS_SCHEDULE_EIP2929 = GAS_SCHEDULE_EIP2200._replace(
    sload_gas=veda_constants.WARM_STORAGE_READ_COST,
    sstore_reset_gas=5000 - veda_constants.COLD_SLOAD_COST,
)

sstore_eip2929 = sstore_eip2929_generic(GAS_SCHEDULE_EIP2929)

ACCESS_LIST_STORAGE_KEY_COST_EIP_2930 = 1900

SSTORE_CLEARS_SCHEDULE_EIP_3529 = (
    GAS_SCHEDULE_EIP2929.sstore_reset_gas
    + ACCESS_LIST_STORAGE_KEY_COST_EIP_2930
)


GAS_SCHEDULE_EIP3529 = GAS_SCHEDULE_EIP2929._replace(
    sstore_clears_schedule=SSTORE_CLEARS_SCHEDULE_EIP_3529
)


sstore_eip3529 = partial(sstore_eip2929_generic, GAS_SCHEDULE_EIP3529)
