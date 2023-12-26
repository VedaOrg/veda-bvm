import itertools

from eth_typing import (
    Address,
)

from veda.abc import (
    TransactionContextAPI,
)
from veda.validation import (
    validate_canonical_address,
    validate_uint256,
)


class BaseTransactionContext(TransactionContextAPI):
    __slots__ = ["_origin", "_log_counter"]

    def __init__(self, origin: Address) -> None:
        # validate_canonical_address(origin, title="TransactionContext.origin")
        self._origin = origin
        self._log_counter = itertools.count()

    def get_next_log_counter(self) -> int:
        return next(self._log_counter)

    @property
    def origin(self) -> Address:
        return self._origin
