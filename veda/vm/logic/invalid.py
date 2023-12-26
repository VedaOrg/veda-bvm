from veda.abc import (
    ComputationAPI,
)
from veda.exceptions import (
    InvalidInstruction,
)
from veda.vm.opcode import (
    Opcode,
)


class InvalidOpcode(Opcode):
    mnemonic = "INVALID"
    gas_cost = 0

    def __init__(self, value: int) -> None:
        self.value = value
        super().__init__()

    def __call__(self, computation: ComputationAPI) -> None:
        raise InvalidInstruction(
            f"Invalid opcode 0x{self.value:x} @ {computation.code.program_counter - 1}"
        )
