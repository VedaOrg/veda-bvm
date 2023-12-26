import json
from pathlib import Path
from typing import (
    Any,
    cast,
    Dict,
    Iterable,
    NamedTuple,
    Tuple,
)

from jsonschema import (
    validate,
    ValidationError as JSONSchemaValidationError,
)

from eth_typing import (
    Address,
    BlockNumber,
    Hash32,
    HexAddress,
    HexStr,
)

from eth_utils import (
    big_endian_to_int,
    decode_hex,
    to_canonical_address,
    to_dict,
    to_int,
    to_tuple,
    ValidationError,
)
from eth_utils.toolz import (
    sliding_window,
)

from veda.typing import (
    AccountDetails,
    GenesisDict,
    VMConfiguration,
    VMFork,
    RawAccountDetails,
)
from veda.vm.forks import (
    VedaVM,
)

RawEIP1085Dict = Dict[str, Any]


class Account(NamedTuple):
    balance: int
    nonce: int
    code: bytes
    storage: Dict[int, int]

    def to_dict(self) -> AccountDetails:
        return AccountDetails({
            'balance': self.balance,
            'nonce': self.nonce,
            'code': self.code,
            'storage': self.storage,
        })


class GenesisParams(NamedTuple):
    nonce: bytes
    difficulty: int
    # coinbase: Address
    timestamp: int
    extra_data: Hash32
    gas_limit: int
    veda_timestamp: int
    veda_block_number: int
    veda_block_hash: Hash32

    def to_dict(self) -> GenesisDict:
        return {
            'block_number': 0,
            'nonce': self.nonce,
            'difficulty': self.difficulty,
            # 'coinbase': self.coinbase,
            'timestamp': self.timestamp,
            'extra_data': self.extra_data,
            'gas_limit': self.gas_limit,
            'veda_timestamp': self.veda_timestamp,
            'veda_block_number': self.veda_block_number,
            'veda_block_hash': self.veda_block_hash,
        }


class GenesisData(NamedTuple):
    chain_id: int
    params: GenesisParams
    state: Dict[Address, Account]
    vm_configuration: VMConfiguration


def get_eip1085_schema() -> Dict[str, Any]:
    base_veda_dir = Path(__file__).parent.parent
    if base_veda_dir.name != 'veda':
        raise RuntimeError(f"Expected to be in root `veda` module. Got: {str(base_veda_dir)}")
    eip1085_schema_path = base_veda_dir / 'assets' / 'eip1085.schema.json'
    with open(eip1085_schema_path) as schema_file:
        eip1085_schema = json.load(schema_file)
    return eip1085_schema


def validate_raw_eip1085_genesis_config(genesis_config: RawEIP1085Dict) -> None:
    """
    Validate that all valid genesis config parameters are present from the decoded
    genesis JSON config specified.
    """
    eip1085_schema = get_eip1085_schema()
    try:
        validate(genesis_config, eip1085_schema)
    except JSONSchemaValidationError as err:
        raise ValidationError(str(err)) from err


def hex_to_block_number(hex_encoded_number: str) -> BlockNumber:
    return BlockNumber(to_int(hexstr=hex_encoded_number))


@to_tuple
def _extract_vm_config(vm_config: Dict[str, str]) -> Iterable[VMFork]:
    if 'vedaForkBlock' in vm_config.keys():
        yield hex_to_block_number(vm_config['vedaForkBlock']), VedaVM
@to_tuple
def _filter_vm_config(vm_config: VMConfiguration) -> Iterable[VMFork]:
    for idx, (fork_block, vm_class) in enumerate(vm_config):
        if fork_block == 0:
            subsequent_fork_blocks = {block_num for block_num, _ in vm_config[idx + 1:]}
            if 0 in subsequent_fork_blocks:
                # we ignore any VMs which are at block 0 and have a subsequent
                # VM which is also at block 0.
                continue
        yield fork_block, vm_class


ALL_VMS = (
    VedaVM
)


@to_tuple
def _normalize_vm_config(vm_config: VMConfiguration) -> Iterable[VMFork]:
    """
    Take the declared vm_configuration and inject the VM for block 0 *if*
    there is no vm set to start at block 0.
    """
    all_fork_blocks = {fork_block for fork_block, _ in vm_config}
    all_fork_names = {vm_class.fork for _, vm_class in vm_config}

    if 0 not in all_fork_blocks:
        for left_vm, right_vm in sliding_window(2, ALL_VMS):
            if right_vm.fork in all_fork_names:
                if left_vm.fork in all_fork_names:
                    # This should be an unreachable code path assuming
                    # `vm_config` has already been validated to have correct
                    # internal ordering for the various VM classes.
                    raise ValidationError(f"Invariant: Found {left_vm} in vm configuration")
                yield cast(BlockNumber, 0), left_vm
                break
        else:
            raise ValidationError("Unable to determine correct fork for block 0")
    yield from vm_config


def extract_vm_configuration(genesis_config: RawEIP1085Dict) -> VMConfiguration:
    """
    Returns a vm configuration which is a tuple of block numbers associated to a fork
    based on the genesis config provided.
    """
    return _normalize_vm_config(_filter_vm_config(_extract_vm_config(genesis_config['params'])))


def extract_genesis_params(genesis_config: RawEIP1085Dict) -> GenesisParams:
    raw_params = genesis_config['genesis']

    return GenesisParams(
        nonce=decode_hex(raw_params['nonce']),
        difficulty=to_int(hexstr=raw_params['difficulty']),
        extra_data=Hash32(decode_hex(raw_params['extraData'])),
        gas_limit=to_int(hexstr=raw_params['gasLimit']),
        # coinbase=Address(decode_hex(raw_params['coinbase'])),
        timestamp=to_int(hexstr=raw_params['timestamp']),
        veda_block_hash=Hash32(decode_hex(raw_params['veda_block_hash'])),
        veda_block_number=raw_params['veda_block_number'],
        veda_timestamp=to_int(hexstr=raw_params['veda_timestamp']),
    )


def extract_chain_id(genesis_config: RawEIP1085Dict) -> int:
    return to_int(hexstr=genesis_config['params']['chainId'])


@to_dict
def _normalize_storage(storage: Dict[HexStr, HexStr]) -> Iterable[Tuple[int, int]]:
    for slot, value in storage.items():
        yield big_endian_to_int(decode_hex(slot)), big_endian_to_int(decode_hex(value))


def _normalize_account(raw_account: RawAccountDetails) -> Account:
    return Account(
        balance=to_int(hexstr=raw_account.get('balance', '0x0')),
        nonce=to_int(hexstr=raw_account.get('nonce', '0x0')),
        code=decode_hex(raw_account.get('code', '')),
        storage=_normalize_storage(raw_account.get('storage', {})),
    )


@to_dict
def _normalize_genesis_state(
        genesis_state: Dict[HexAddress, RawAccountDetails]) -> Iterable[Tuple[Address, Account]]:
    for address, account in genesis_state.items():
        yield to_canonical_address(address), _normalize_account(account)


def extract_genesis_state(genesis_config: Dict[str, Any]) -> Dict[Address, Account]:
    if 'accounts' in genesis_config:
        return _normalize_genesis_state(genesis_config['accounts'])
    else:
        return {}


def extract_genesis_data(raw_genesis_config: RawEIP1085Dict) -> GenesisData:
    # version = raw_genesis_config['version']
    # if version != '1':
    #     raise ValueError(f"Unsupported version: {version}")

    state = extract_genesis_state(raw_genesis_config)
    params = extract_genesis_params(raw_genesis_config)
    vm_configuration = extract_vm_configuration(raw_genesis_config)
    chain_id = extract_chain_id(raw_genesis_config)

    return GenesisData(
        chain_id=chain_id,
        params=params,
        state=state,
        vm_configuration=vm_configuration,
    )
