from typing import (
    Any,
    Union,
)

from veda._utils.spoof import (
    SpoofAttributes,
)
from veda.abc import (
    SignedTransactionAPI,
)


class SpoofTransaction(SpoofAttributes):
    def __init__(
        self,
        transaction: Union[SignedTransactionAPI],
        **overrides: Any
    ) -> None:
        super().__init__(transaction, **overrides)
