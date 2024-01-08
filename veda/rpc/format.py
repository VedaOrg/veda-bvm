import functools
from typing import (
    Any,
    Callable,
    cast,
    Dict,
    Iterable,
    List,
    Sequence,
    Tuple,
    Union,
)
from eth_utils.toolz import (
    compose,
    merge,
)

from eth_utils import (
    apply_formatter_if,
    apply_formatters_to_dict,
    decode_hex,
    encode_hex,
    int_to_big_endian,
    is_address,
    to_checksum_address,
)
from eth_typing import (
    Address,
)

import rlp

from veda.abc import (
    BlockAPI,
    BlockHeaderAPI,
    ReceiptAPI,
    SignedTransactionAPI, LogAPI,
)
from veda.constants import (
    CREATE_CONTRACT_ADDRESS, ZERO_ADDRESS, ZERO_HASH32,
)

from veda.rpc.base import AsyncChainAPI
from veda.rpc.types import (
    RpcAccessList,
    RpcBlockResponse,
    RpcBlockTransactionResponse,
    RpcHeaderResponse,
    RpcReceiptResponse,
    RpcTransactionResponse,
)
# from veda._utils.address import generate_contract_address

from veda._utils.address import generate_contract_address

def format_bloom(bloom: int) -> str:
    formatted_bloom = encode_hex(int_to_big_endian(bloom))[2:]
    formatted_bloom = '0x' + formatted_bloom.rjust(512, '0')
    return formatted_bloom


def to_log_dict(block: BlockAPI, log: LogAPI, transaction: SignedTransactionAPI, idx: int) -> Dict[str, Any]:
    return {
        "address": to_checksum_address(log.address),
        "blockHash": encode_hex(block.hash),
        "blockNumber": hex(block.number),
        "data": encode_hex(log.data),
        "logIndex": hex(idx),
        "removed": False,
        "topics": [encode_hex(topic.to_bytes(32, 'big')) for topic in log.topics],
        "transactionHash": encode_hex(transaction.hash),
        "transactionIndex": hex(idx),
    }


def to_receipt_response(receipt: ReceiptAPI,
                        transaction: SignedTransactionAPI,
                        index: int,
                        header: BlockHeaderAPI,
                        tx_gas_used: int) -> RpcReceiptResponse:

    if transaction.to == CREATE_CONTRACT_ADDRESS:
        contract_address = encode_hex(
            generate_contract_address(transaction.sender, transaction.nonce)
        )
    else:
        contract_address = None

    block_hash = encode_hex(header.hash)
    block_number = hex(header.block_number)
    receipt_and_transaction_index = hex(index)
    transaction_hash = encode_hex(transaction.hash)

    return {
        "blockHash": block_hash,
        "blockNumber": block_number,
        "contractAddress": contract_address,
        "cumulativeGasUsed": hex(receipt.gas_used),
        "from": encode_hex(transaction.sender),
        'gasUsed': hex(tx_gas_used) if tx_gas_used >= 0 else hex(0),
        "logs": [
            {
                "address": encode_hex(log.address),
                "data": encode_hex(log.data),
                "blockHash": block_hash,
                "blockNumber": block_number,
                "logIndex": receipt_and_transaction_index,
                # We only serve receipts from transactions that ended up in the canonical chain
                # which means this can never be `True`
                "removed": False,
                "topics": [
                    encode_hex(int_to_big_endian(topic).rjust(32, b'\x00')) for topic in log.topics
                ],
                "transactionHash": transaction_hash,
                "transactionIndex": receipt_and_transaction_index,
            }
            for log in receipt.logs
        ],
        "logsBloom": format_bloom(receipt.bloom),
        "status": "0x00" if receipt.state_root == b'' else encode_hex(receipt.state_root),  # be compatible with previous db
        "to": apply_formatter_if(
            is_address,
            to_checksum_address,
            encode_hex(transaction.to)
        ),
        "transactionHash": transaction_hash,
        "transactionIndex": receipt_and_transaction_index,
    }


def access_list_to_json(
        access_list: Iterable[Tuple[Address, Iterable[int]]]
) -> List[RpcAccessList]:

    return [
        {
            "address": to_checksum_address(address),
            "storageKeys": [hex(slot) for slot in storage_slots],
        }
        for address, storage_slots in access_list
    ]


def transaction_to_dict(transaction: SignedTransactionAPI) -> RpcTransactionResponse:
    address_from = to_checksum_address(transaction.sender)
    address_to = apply_formatter_if(
            is_address,
            to_checksum_address,
            encode_hex(transaction.to))

    if address_from == '0x':
        address_from = None

    if address_to == '0x':
        address_to = None

    base_dict = {
        'hash': encode_hex(transaction.hash),
        'nonce': hex(transaction.nonce),
        'gas': hex(transaction.gas),
        'from': address_from,
        'to': address_to,
        'input': encode_hex(transaction.data),
        'chainId': hex(transaction.chain_id) if transaction.chain_id else None,

        'value': hex(0),
        'gasPrice': hex(0),
        'gasUsed': hex(0),
        # 'transactionIndex': transaction.transaction_index,
        # compatible with explorer
        "r": hex(0),
        "s": hex(0),
        "v": hex(0),
    }
    #
    # if transaction.type_id is None:
    #     legacy_txn = cast(LegacyTransactionFieldsAPI, transaction)
    #     return merge(base_dict, {
    #         'v': hex(legacy_txn.v),
    #     })
    # elif transaction.type_id == 1:
    #     return merge(base_dict, {
    #         'accessList': access_list_to_json(transaction.access_list),
    #         'type': hex(transaction.type_id),
    #     })
    # else:
    #     raise NotImplementedError(f"Cannot this type of transaction: {transaction!r}")

    return base_dict


async def block_transaction_to_dict(chain: AsyncChainAPI,
                              transaction: SignedTransactionAPI,
                              header: BlockHeaderAPI) -> RpcBlockTransactionResponse:
    data = cast(RpcBlockTransactionResponse, transaction_to_dict(transaction))
    data['blockHash'] = encode_hex(header.hash)
    data['blockNumber'] = hex(header.block_number)

    block_num, index = await chain.coro_get_canonical_transaction_index(transaction.hash)
    data['transactionIndex'] = hex(index)

    return data


hexstr_to_int = functools.partial(int, base=16)


TRANSACTION_NORMALIZER = {
    'data': decode_hex,
    'from': decode_hex,
    'gas': hexstr_to_int,
    'gasPrice': hexstr_to_int,
    'nonce': hexstr_to_int,
    'to': decode_hex,
    'value': hexstr_to_int,
}

SAFE_TRANSACTION_DEFAULTS = {
    'data': b'',
    'to': CREATE_CONTRACT_ADDRESS,
    'value': 0,
}


def normalize_transaction_dict(transaction_dict: Dict[str, str]) -> Dict[str, Any]:
    normalized_dict = apply_formatters_to_dict(TRANSACTION_NORMALIZER, transaction_dict)
    return merge(SAFE_TRANSACTION_DEFAULTS, normalized_dict)


def header_to_dict(header: BlockHeaderAPI) -> RpcHeaderResponse:
    return {
        "difficulty": hex(header.difficulty),
        "extraData": encode_hex(header.extra_data),
        # "extraData": "0x",
        "gasLimit": hex(header.gas_limit),
        "gasUsed": hex(header.gas_used),
        "hash": encode_hex(header.hash),
        "logsBloom": format_bloom(header.bloom),
        "miner": encode_hex(ZERO_ADDRESS),  # Dummy for ETH RPC compatible
        "mixHash": encode_hex(header.mix_hash),
        # "nonce": encode_hex(header.nonce),
        "nonce": encode_hex(b"\x00\x00\x00\x00\x00\x00\x00\x00"),
        "number": hex(header.block_number),
        "parentHash": encode_hex(header.parent_hash),
        "receiptsRoot": encode_hex(header.receipt_root),
        "sha3Uncles": encode_hex(ZERO_HASH32),  # Dummy for ETH RPC compatible
        "stateRoot": encode_hex(header.state_root),
        "timestamp": hex(header.timestamp),
        "transactionsRoot": encode_hex(header.transaction_root),
        "baseFeePerGas": hex(0)
        # "miner": encode_hex(header.coinbase),
    }

async def block_to_dict(block: BlockAPI,
                  chain: AsyncChainAPI,
                  include_transactions: bool) -> RpcBlockResponse:

    # There doesn't seem to be a type safe way to initialize the RpcBlockResponse from
    # a RpcHeaderResponse + the extra fields hence the cast here.
    response = cast(RpcBlockResponse, header_to_dict(block.header))

    if include_transactions:
        txs: Union[Sequence[str], Sequence[RpcBlockTransactionResponse]] = [
            await block_transaction_to_dict(chain, tx, block.header) for tx in block.transactions
        ]

    else:
        txs = [encode_hex(tx.hash) for tx in block.transactions]

    response['totalDifficulty'] = hex(chain.get_score(block.hash))
    # response['uncles'] = [encode_hex(uncle.hash) for uncle in block.uncles]
    response['uncles'] = []
    response['size'] = hex(len(rlp.encode(block)))
    response['transactions'] = txs

    return response


def format_params(*formatters: Any) -> Callable[..., Any]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def formatted_func(self: Any, *args: Any) -> Callable[..., Any]:
            if len(formatters) != len(args):
                raise TypeError("could not apply %d formatters to %r" % (len(formatters), args))
            formatted = (formatter(arg) for formatter, arg in zip(formatters, args))
            return await func(self, *formatted)
        return formatted_func
    return decorator


def to_int_if_hex(value: Any) -> Any:
    if isinstance(value, str) and value.startswith('0x'):
        return int(value, 16)
    else:
        return value


def empty_to_0x(val: str) -> str:
    if val:
        return val
    else:
        return '0x'


def to_lower(val: str) -> str:
    return val.lower()


remove_leading_zeros = compose(hex, functools.partial(int, base=16))
