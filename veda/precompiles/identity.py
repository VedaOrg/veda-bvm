from veda import (
    constants,
)
from veda._utils.numeric import (
    ceil32,
)
from veda.abc import (
    ComputationAPI,
)


def identity(computation: ComputationAPI) -> ComputationAPI:
    word_count = ceil32(len(computation.msg.data)) // 32
    gas_fee = constants.GAS_IDENTITY + word_count * constants.GAS_IDENTITYWORD

    computation.consume_gas(gas_fee, reason="Identity Precompile")

    computation.output = computation.msg.data_as_bytes
    return computation
