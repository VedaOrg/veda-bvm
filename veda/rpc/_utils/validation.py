import inspect
from typing import (
    Any,
    Dict,
)

from eth_utils import (
    is_address,
)

from veda.abc import (
    VirtualMachineAPI,
)



FORBIDDEN_KEYS = {'v', 'r', 's', 'nonce'}
DERIVED_KEYS = {'from'}
RENAMED_KEYS = {}


def validate_transaction_gas_estimation_dict(transaction_dict: Dict[str, Any],
                                             vm: VirtualMachineAPI) -> None:
    """Validate a transaction dictionary supplied for an RPC method call"""
    transaction_signature = inspect.signature(vm.get_transaction_builder().new_transaction)

    all_keys = set(transaction_signature.parameters.keys())
    allowed_keys = all_keys.difference(FORBIDDEN_KEYS).union(DERIVED_KEYS)
    spec_keys = set(RENAMED_KEYS.get(field_name, field_name) for field_name in allowed_keys)

    superfluous_keys = set(transaction_dict).difference(spec_keys)

    if superfluous_keys:
        raise ValueError(
            "The following invalid fields were given in a transaction: %r. Only %r are allowed" % (
                list(sorted(superfluous_keys)),
                list(sorted(spec_keys)),
            )
        )


def validate_transaction_call_dict(transaction_dict: Dict[str, Any], vm: VirtualMachineAPI) -> None:
    validate_transaction_gas_estimation_dict(transaction_dict, vm)

    # 'to' is required in a call, but not a gas estimation
    if not is_address(transaction_dict.get('to', None)):
        raise ValueError("The 'to' field must be supplied when getting the result of a transaction")
