import hashlib

from veda import (
    constants,
)
from veda._utils.numeric import (
    ceil32,
)
from veda._utils.padding import (
    pad32,
)
from veda.abc import (
    ComputationAPI,
)


def ripemd160(computation: ComputationAPI) -> ComputationAPI:
    word_count = ceil32(len(computation.msg.data)) // 32
    gas_fee = constants.GAS_RIPEMD160 + word_count * constants.GAS_RIPEMD160WORD

    computation.consume_gas(gas_fee, reason="RIPEMD160 Precompile")

    # TODO: this only works if openssl is installed.
    hash = hashlib.new("ripemd160", computation.msg.data).digest()
    padded_hash = pad32(hash)
    computation.output = padded_hash
    return computation
