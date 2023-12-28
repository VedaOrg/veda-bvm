import os

import rlp
from eth_utils.toolz import (
    identity,
)
from typing import (
    Any,
    cast,
    Dict,
    List,
    NoReturn,
    Union,
)

from lahja import EndpointAPI
from mypy_extensions import (
    TypedDict,
)

from eth_typing import (
    Address,
    BlockNumber,
    Hash32,
    HexStr,
)
from eth_utils import (
    decode_hex,
    encode_hex,
    int_to_big_endian,
    is_integer,
    to_hex,
    to_wei,
    ValidationError,
)

from veda.abc import (
    BlockAPI,
    BlockHeaderAPI,
    SignedTransactionAPI,
    StateAPI,
)
from veda.constants import (
    ZERO_ADDRESS,
)
from veda.exceptions import (
    HeaderNotFound,
    TransactionNotFound,
)
from veda.vm.forks.veda import VedaBlock

from veda.vm.spoof import (
    SpoofTransaction,
)
from veda._utils.padding import (
    pad32,
)

from veda.rpc.base import AsyncChainAPI
from veda.config import VedaConfig
from veda.constants import (
    TO_NETWORKING_BROADCAST_CONFIG,
)
from veda.rpc.exceptions import RpcError
from veda.rpc.format import (
    block_to_dict,
    header_to_dict,
    format_params,
    normalize_transaction_dict,
    to_int_if_hex,
    to_receipt_response,
    transaction_to_dict, to_log_dict,
)
from veda.rpc.modules.base import (
    Eth1ChainRPCModule,
)
from veda.rpc.modules._util import (
    get_header,
)
from veda.rpc.retry import retryable
from veda.rpc.types import (
    RpcBlockResponse,
    RpcHeaderResponse,
    RpcReceiptResponse,
    RpcTransactionResponse,
)
from veda.sync.common.events import (
    SyncingRequest,
    SendLocalTransaction,
)
from veda.rpc._utils.transactions import DefaultTransactionValidator
from veda.rpc._utils.validation import (
    validate_transaction_call_dict,
    validate_transaction_gas_estimation_dict, validate_filter_params,
)


async def state_at_block(
        chain: AsyncChainAPI,
        at_block: Union[str, int],
        read_only: bool = True) -> StateAPI:
    at_header = await get_header(chain, at_block)
    vm = chain.get_vm(at_header)
    return vm.state


async def get_block_at_number(chain: AsyncChainAPI, at_block: Union[str, int]) -> BlockAPI:
    # mypy doesn't have user defined type guards yet
    # https://github.com/python/mypy/issues/5206
    if is_integer(at_block) and at_block >= 0:  # type: ignore
        # optimization to avoid requesting block, then header, then block again
        return await chain.coro_get_canonical_block_by_number(cast(BlockNumber, at_block))
    else:
        at_header = await get_header(chain, at_block)
        return await chain.coro_get_block_by_header(at_header)


def dict_to_spoof_transaction(
        chain: AsyncChainAPI,
        header: BlockHeaderAPI,
        transaction_dict: Dict[str, Any]) -> SignedTransactionAPI:
    """
    Convert dicts used in calls & gas estimates into a spoof transaction
    """
    txn_dict = normalize_transaction_dict(transaction_dict)
    sender = txn_dict.get('from', ZERO_ADDRESS)

    if 'nonce' in txn_dict:
        nonce = txn_dict['nonce']
    else:
        vm = chain.get_vm(header)
        nonce = vm.state.get_nonce(sender)

    gas = txn_dict.get('gas', header.gas_limit)

    tx = chain.get_vm_class(header).create_transaction(
        nonce=nonce,
        gas=gas,
        to=txn_dict['to'],
        data=txn_dict['data'],
        veda_sender=txn_dict['veda_sender'],
        veda_txhash=ZERO_ADDRESS
    )


    return cast(SignedTransactionAPI, SpoofTransaction(tx, sender=sender, veda_sender=sender))


class SyncProgressDict(TypedDict):
    startingBlock: BlockNumber
    currentBlock: BlockNumber
    highestBlock: BlockNumber


class Eth(Eth1ChainRPCModule):
    """
    All the methods defined by JSON-RPC API, starting with "eth_"...

    Any attribute without an underscore is publicly accessible.
    """

    def __init__(self,
                 chain: AsyncChainAPI,
                 event_bus: EndpointAPI,
                 veda_config: VedaConfig) -> None:
        self.veda_config = veda_config
        super().__init__(chain, event_bus)

    async def accounts(self) -> List[str]:
        # veda does not manage accounts for the user
        return []

    async def blockNumber(self) -> str:
        num = self.chain.get_canonical_head().block_number
        return hex(num)

    async def chainId(self) -> str:
        chain_id = self.chain.chain_id
        return to_hex(chain_id)

    @format_params(identity, to_int_if_hex)
    @retryable(which_block_arg_name='at_block')
    async def call(self, txn_dict: Dict[str, Any], at_block: Union[str, int]) -> str:
        # VEDA: Fill veda_sender with the sender address or 0xff...ff if not specified
        if 'veda_sender' not in txn_dict:
            txn_dict['veda_sender'] = txn_dict.get('from', 20 * b"\x00")

        header = await get_header(self.chain, at_block)
        validate_transaction_call_dict(txn_dict, self.chain.get_vm(header))
        transaction = dict_to_spoof_transaction(self.chain, header, txn_dict)
        result = self.chain.get_transaction_result(transaction, header)
        return encode_hex(result)

    async def coinbase(self) -> str:
        raise NotImplementedError("Veda does not support mining")

    @format_params(identity, to_int_if_hex)
    @retryable(which_block_arg_name='at_block')
    async def estimateGas(self, txn_dict: Dict[str, Any], at_block: Union[str, int]) -> str:
        header = await get_header(self.chain, at_block)
        validate_transaction_gas_estimation_dict(txn_dict, self.chain.get_vm(header))
        transaction = dict_to_spoof_transaction(self.chain, header, txn_dict)
        gas = self.chain.estimate_gas(transaction, header)
        return hex(gas)

    async def gasPrice(self) -> str:
        return hex(int(os.environ.get('VEDA_GAS_PRICE', to_wei(1, 'gwei'))))

    @format_params(decode_hex, to_int_if_hex)
    @retryable(which_block_arg_name='at_block')
    async def getBalance(self, address: Address, at_block: Union[str, int]) -> str:
        state = await state_at_block(self.chain, at_block)
        balance = state.get_balance(address)

        return hex(balance)

    async def getWork(self) -> NoReturn:
        raise NotImplementedError("Veda does not support mining")

    @format_params(decode_hex, decode_hex, decode_hex)
    async def submitWork(self, nonce: bytes, pow_hash: Hash32, mix_digest: Hash32) -> NoReturn:
        raise NotImplementedError("Veda does not support mining")

    @format_params(decode_hex, decode_hex)
    async def submitHashrate(self, hashrate: Hash32, id: Hash32) -> NoReturn:
        raise NotImplementedError("Veda does not support mining")

    @format_params(decode_hex, identity)
    async def getBlockByHash(self,
                             block_hash: Hash32,
                             include_transactions: bool) -> RpcBlockResponse:
        block = await self.chain.coro_get_block_by_hash(block_hash)
        return block_to_dict(block, self.chain, include_transactions)

    @format_params(to_int_if_hex, identity)
    async def getBlockByNumber(self,
                               at_block: Union[str, int],
                               include_transactions: bool) -> RpcBlockResponse:
        block = await get_block_at_number(self.chain, at_block)
        return block_to_dict(block, self.chain, include_transactions)

    @format_params(decode_hex)
    async def getBlockTransactionCountByHash(self, block_hash: Hash32) -> str:
        block = await self.chain.coro_get_block_by_hash(block_hash)
        return hex(len(block.transactions))

    @format_params(to_int_if_hex)
    async def getBlockTransactionCountByNumber(self, at_block: Union[str, int]) -> str:
        block = await get_block_at_number(self.chain, at_block)
        return hex(len(block.transactions))

    @format_params(decode_hex, to_int_if_hex)
    @retryable(which_block_arg_name='at_block')
    async def getCode(self, address: Address, at_block: Union[str, int]) -> str:
        state = await state_at_block(self.chain, at_block)
        code = state.get_code(address)
        return encode_hex(code)

    @format_params(decode_hex, to_int_if_hex, to_int_if_hex)
    @retryable(which_block_arg_name='at_block')
    async def getStorageAt(self, address: Address, position: int, at_block: Union[str, int]) -> str:
        if not is_integer(position) or position < 0:
            raise TypeError("Position of storage must be a whole number, but was: %r" % position)

        state = await state_at_block(self.chain, at_block)
        stored_val = state.get_storage(address, position)

        return encode_hex(pad32(int_to_big_endian(stored_val)))

    @format_params(decode_hex)
    async def getTransactionByHash(self,
                                   transaction_hash: Hash32) -> RpcTransactionResponse:
        transaction = await self.chain.coro_get_canonical_transaction(transaction_hash)
        return transaction_to_dict(transaction)

    @format_params(decode_hex, to_int_if_hex)
    async def getTransactionByBlockHashAndIndex(self,
                                                block_hash: Hash32,
                                                index: int) -> RpcTransactionResponse:
        block = await self.chain.coro_get_block_by_hash(block_hash)
        transaction = block.transactions[index]
        return transaction_to_dict(transaction)

    @format_params(to_int_if_hex, to_int_if_hex)
    async def getTransactionByBlockNumberAndIndex(self,
                                                  at_block: Union[str, int],
                                                  index: int) -> RpcTransactionResponse:
        block = await get_block_at_number(self.chain, at_block)
        transaction = block.transactions[index]
        return transaction_to_dict(transaction)

    @format_params(decode_hex, to_int_if_hex)
    @retryable(which_block_arg_name='at_block')
    async def getTransactionCount(self, address: Address, at_block: Union[str, int]) -> str:

        state = await state_at_block(self.chain, at_block)
        nonce = state.get_nonce(address)
        return hex(nonce)

    @format_params(decode_hex)
    async def getTransactionReceipt(self,
                                    transaction_hash: Hash32) -> RpcReceiptResponse:

        try:
            tx_block_number, tx_index = await self.chain.coro_get_canonical_transaction_index(
                transaction_hash,
            )
        except TransactionNotFound as exc:
            raise RpcError(
                f"Transaction {encode_hex(transaction_hash)} is not in the canonical chain"
            ) from exc

        try:
            block_header = await self.chain.coro_get_canonical_block_header_by_number(
                tx_block_number
            )
        except HeaderNotFound as exc:
            raise RpcError(
                f"Block {tx_block_number} is not in the canonical chain"
            ) from exc

        try:
            transaction = await self.chain.coro_get_canonical_transaction_by_index(
                tx_block_number,
                tx_index
            )
        except TransactionNotFound as exc:
            raise RpcError(
                f"Transaction {encode_hex(transaction_hash)} is not in the canonical chain"
            ) from exc

        if transaction.hash != transaction_hash:
            raise RpcError(
                f"Unexpected transaction {encode_hex(transaction.hash)} at index {tx_index}"
            )

        receipt = await self.chain.coro_get_transaction_receipt_by_index(
            tx_block_number,
            tx_index
        )

        if tx_index > 0:
            previous_receipt = await self.chain.coro_get_transaction_receipt_by_index(
                tx_block_number,
                tx_index - 1
            )
            # The receipt only tells us the cumulative gas that was used. To find the gas used by
            # the transaction alone we have to get the previous receipt and calculate the
            # difference.
            tx_gas_used = receipt.gas_used - previous_receipt.gas_used
        else:
            tx_gas_used = receipt.gas_used

        return to_receipt_response(receipt, transaction, tx_index, block_header, tx_gas_used)

    @format_params(decode_hex)
    async def getUncleCountByBlockHash(self, block_hash: Hash32) -> str:
        block = await self.chain.coro_get_block_by_hash(block_hash)
        return hex(len(block.uncles))

    @format_params(to_int_if_hex)
    async def getUncleCountByBlockNumber(self, at_block: Union[str, int]) -> str:
        block = await get_block_at_number(self.chain, at_block)
        return hex(len(block.uncles))

    @format_params(decode_hex, to_int_if_hex)
    async def getUncleByBlockHashAndIndex(self,
                                          block_hash: Hash32,
                                          index: int) -> RpcHeaderResponse:
        # block = await self.chain.coro_get_block_by_hash(block_hash)
        # uncle = block.uncles[index]
        # return header_to_dict(uncle)
        raise NotImplementedError("getUncleByBlockHashAndIndex is not supported")

    @format_params(to_int_if_hex, to_int_if_hex)
    async def getUncleByBlockNumberAndIndex(self,
                                            at_block: Union[str, int],
                                            index: int) -> RpcHeaderResponse:
        # block = await get_block_at_number(self.chain, at_block)
        # uncle = block.uncles[index]
        # return header_to_dict(uncle)

        raise NotImplementedError("getUncleByBlockNumberAndIndex is not supported")

    async def getLogs(self, filter_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Validate the filter params
        filter_params = validate_filter_params(filter_params)

        if filter_params.blockHash:
            # validate the block hash
            block = await self.chain.coro_get_block_by_hash(decode_hex(filter_params.blockHash))
            filter_params.fromBlock = block.header.block_number
            filter_params.toBlock = block.header.block_number
            from_block = block.header.block_number
            to_block = block.header.block_number
        else:
            current_header = await self.chain.coro_get_canonical_head()
            if filter_params.fromBlock is None:
                filter_params.fromBlock = current_header.block_number
            if filter_params.toBlock is None:
                filter_params.toBlock = current_header.block_number

            from_block = int(filter_params.fromBlock, 16)
            to_block = int(filter_params.toBlock, 16)

        resp = []
        for block_number in range(from_block, to_block + 1):
            block = cast(VedaBlock, await self.chain.coro_get_canonical_block_by_number(block_number))

            receipts = block.get_receipts(self.chain.chaindb)
            for idx, (transaction, receipt) in enumerate(zip(block.transactions, receipts)):
                for log in receipt.logs:
                    # filter address field
                    if filter_params.address:
                        if isinstance(filter_params.address, str):
                            address_filter = [decode_hex(filter_params.address)]
                        else:
                            address_filter = [decode_hex(address) for address in filter_params.address]

                        if log.address not in address_filter:
                            continue

                    # filter topics field
                    if filter_params.topics:
                        if len(filter_params.topics) >= 4:
                            raise ValidationError("Topics param length is too long")

                        topics_filtered = False
                        for idx in range(min(len(filter_params.topics), len(log.topics))):
                            if (filter_params.topics[idx] is not None
                                    and int.from_bytes(decode_hex(filter_params.topics[idx]), 'big') != log.topics[idx]):
                                topics_filtered = True
                                break

                        if topics_filtered:
                            continue

                    data = to_log_dict(block, log, transaction, idx)
                    resp.append(data)
        return resp

    @format_params(decode_hex)
    async def sendRawTransaction(self,
                                 transaction_bytes: bytes) -> HexStr:

        # serialized_txn = rlp.decode(transaction_bytes)
        # # TODO on pyevm upgrade, switch to:
        # # transaction_builder = self.chain.get_vm().get_transaction_builder()
        # # transaction = transaction_builder.decode(transaction_bytes)
        #
        # validator = DefaultTransactionValidator.from_network_id(
        #     self.chain,
        #     self.veda_config.network_id,
        # )
        #
        # try:
        #     transaction = validator.validate(serialized_txn)
        # except ValidationError as err:
        #     raise RpcError(err) from err
        # else:
        #     await self.event_bus.broadcast(SendLocalTransaction(transaction))
        #     return encode_hex(transaction.hash)

        raise NotImplementedError("sendRawTransaction is not supported")

    async def hashrate(self) -> str:
        raise NotImplementedError("hashrate is not supported")

    async def mining(self) -> bool:
        return False

    async def protocolVersion(self) -> str:
        return "63"

    async def syncing(self) -> Union[bool, SyncProgressDict]:
        res = await self.event_bus.request(SyncingRequest(), TO_NETWORKING_BROADCAST_CONFIG)
        if res.is_syncing:
            return {
                "startingBlock": res.progress.starting_block,
                "currentBlock": res.progress.current_block,
                "highestBlock": res.progress.highest_block
            }
        return False
