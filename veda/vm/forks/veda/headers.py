from typing import (
    TYPE_CHECKING,
    Any, Optional, Dict,
)

from eth_typing import Address, BlockNumber
from toolz import curry

from veda._utils.db import (
    get_parent_header,
)
from veda._utils.headers import (
    compute_gas_limit,
    new_timestamp_from_parent,
)
from veda.abc import (
    BlockHeaderAPI,
)
from veda.constants import (
    BOMB_EXPONENTIAL_FREE_PERIODS,
    BOMB_EXPONENTIAL_PERIOD,
    DIFFICULTY_ADJUSTMENT_DENOMINATOR,
    DIFFICULTY_MINIMUM,
    GENESIS_GAS_LIMIT, ZERO_ADDRESS, GENESIS_PARENT_HASH, GENESIS_BLOCK_NUMBER, BLANK_ROOT_HASH,
)
from veda.rlp.headers import (
    BlockHeader,
)
from veda.typing import HeaderParams
from veda.validation import (
    validate_gt,
    validate_header_params_for_configuration,
)
from .blocks import VedaBlockHeader

from .constants import (
    FRONTIER_DIFFICULTY_ADJUSTMENT_CUTOFF,
)

if TYPE_CHECKING:
    from veda.vm.forks.veda import VedaVM  # noqa: F401

def compute_veda_difficulty(parent_header: BlockHeaderAPI, timestamp: int) -> int:
    # TODO: VEDA/ don't know the logics
    return 0


def fill_header_params_from_parent(
    parent: BlockHeaderAPI,
    gas_limit: int,
    difficulty: int,
    timestamp: int,
    # coinbase: Address = ZERO_ADDRESS,
    nonce: bytes = None,
    extra_data: bytes = None,
    transaction_root: bytes = None,
    state_root: bytes = None,
    mix_hash: bytes = None,
    receipt_root: bytes = None,
    block_number: int = None,
    veda_timestamp: int = None,
    veda_block_number: int = None,
    veda_block_hash: bytes = None,
) -> Dict[str, HeaderParams]:
    if parent is None:
        parent_hash = GENESIS_PARENT_HASH
        block_number = GENESIS_BLOCK_NUMBER
        if state_root is None:
            state_root = BLANK_ROOT_HASH
    else:
        parent_hash = parent.hash
        block_number = BlockNumber(parent.block_number + 1)

        if state_root is None:
            state_root = parent.state_root

    header_kwargs: Dict[str, HeaderParams] = {
        "parent_hash": parent_hash,
        # "coinbase": coinbase,
        "state_root": state_root,
        "gas_limit": gas_limit,
        "difficulty": difficulty,
        "block_number": block_number,
        "timestamp": timestamp,
    }
    # if nonce is not None:
    #     header_kwargs["nonce"] = nonce
    if extra_data is not None:
        header_kwargs["extra_data"] = extra_data
    if transaction_root is not None:
        header_kwargs["transaction_root"] = transaction_root
    if receipt_root is not None:
        header_kwargs["receipt_root"] = receipt_root
    if mix_hash is not None:
        header_kwargs["mix_hash"] = mix_hash
    if veda_timestamp is not None:
        header_kwargs["veda_timestamp"] = veda_timestamp
    if veda_block_number is not None:
        header_kwargs["veda_block_number"] = veda_block_number
    if veda_block_hash is not None:
        header_kwargs["veda_block_hash"] = veda_block_hash

    return header_kwargs

@curry
def create_veda_header_from_parent(
    parent_header: Optional[BlockHeaderAPI],
    **header_params: Any,
) -> BlockHeaderAPI:
    if "timestamp" not in header_params:
        header_params["timestamp"] = new_timestamp_from_parent(parent_header)

    if "difficulty" not in header_params:
        # Use setdefault to ensure the new header has the same timestamp we use to
        # calculate its difficulty.
        header_params["difficulty"] = compute_veda_difficulty(
            parent_header,
            header_params["timestamp"],
        )
    if "gas_limit" not in header_params:
        header_params["gas_limit"] = 10485760

    all_fields = fill_header_params_from_parent(parent_header, **header_params)
    return VedaBlockHeader(**all_fields)


def configure_veda_header(vm: "VedaVM", **header_params: Any) -> BlockHeader:
    validate_header_params_for_configuration(header_params)

    with vm.get_header().build_changeset(**header_params) as changeset:
        if "timestamp" in header_params and vm.get_header().block_number > 0:
            parent_header = get_parent_header(changeset.build_rlp(), vm.chaindb)
            changeset.difficulty = compute_veda_difficulty(
                parent_header,
                header_params["timestamp"],
            )

        header = changeset.commit()
    return header
