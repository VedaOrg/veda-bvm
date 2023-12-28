import inspect
from typing import (
    Any,
    Dict, Union,
)

from eth_typing import Hash32, Address, BlockIdentifier
from eth_utils import (
    is_address,
)
from pydantic import BaseModel

from veda.abc import (
    VirtualMachineAPI,
)
from typing import List, Optional
from pydantic import BaseModel
from pydantic.types import conint, conbytes



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

class FilterQuery(BaseModel):
    blockHash: Optional[str] = None
    fromBlock: Optional[str] = None
    toBlock: Optional[str] = None
    address: Optional[Union[List[str], str]] = None
    topics: Optional[List[Union[str, None]]] = None

def validate_filter_params(filter_params: Dict[str, Any]) -> FilterQuery:
    '''
    Validation rules
    The filter options:
        fromBlock: QUANTITY|TAG - (optional, default: "latest") Integer block number, or "latest" for the last mined block or "pending", "earliest" for not yet mined transactions.
        toBlock: QUANTITY|TAG - (optional, default: "latest") Integer block number, or "latest" for the last mined block or "pending", "earliest" for not yet mined transactions.
        address: DATA|Array, 20 Bytes - (optional) Contract address or a list of addresses from which logs should originate.
        topics: Array of DATA, - (optional) Array of 32 Bytes DATA topics. Topics are order-dependent. Each topic can also be an array of DATA with "or" options.
        blockhash: DATA, 32 Bytes - (optional, future) With the addition of EIP-234, blockHash will be a new filter option which restricts the logs returned to the single block with the 32-byte hash blockHash. Using blockHash is equivalent to fromBlock = toBlock = the block number with hash blockHash. If blockHash is present in the filter criteria, then neither fromBlock nor toBlock are allowed.
    '''

    return FilterQuery.model_validate(filter_params)
