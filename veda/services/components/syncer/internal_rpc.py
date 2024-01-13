import json
import time
from typing import (
    Any,
    Dict,
    List,
    Sequence,
    Tuple,
    Union,
    Type, cast,
)

import eth_utils
import lahja
import pydantic

from veda.abc import VedaBlockHeaderAPI
from veda.constants import FIRE_AND_FORGET_BROADCASTING
from eth_utils import (
    get_logger,
    ValidationError,
    ExtendedDebugLogger, decode_hex, encode_hex,
)

from lahja import EndpointAPI

from veda.events import NewBlockImportStarted, NewBlockImportFinished, NewBlockImportCanceled
from veda.exceptions import VMError
from veda.rpc.base import AsyncChainAPI
from veda.rpc.chain import VedaAsyncChain
from veda.sync.common.events import NewBlockImported
from pydantic import BaseModel, Field

from veda.vm.forks.veda.blocks import VedaBlockHeader
from veda.vm.forks.veda.transactions import VedaTransaction
from veda.vm.interrupt import EVMMissingData

REQUIRED_REQUEST_KEYS = {
    'id',
    'jsonrpc',
    'method',
}

class SyncBlockModel(BaseModel):
    blockHash: str
    blockNumber: int
    mixHash: str
    timestamp: int

class SyncTransactionModel(BaseModel):
    sender: str
    to: str
    nonce: int
    data: str
    txHash: str


def validate_request(request: Dict[str, Any]) -> None:
    missing_keys = REQUIRED_REQUEST_KEYS - set(request.keys())
    if missing_keys:
        raise ValueError("request must include the keys: %r" % missing_keys)

def generate_response(request: Dict[str, Any], result: Any, error: Union[Exception, str]) -> str:
    response = {
        'jsonrpc': request.get('jsonrpc', "2.0"),
        'id': request.get('id', -1),
    }

    if error is None:
        response['result'] = result
    elif result is not None:
        raise ValueError("Must not supply both a result and an error for JSON-RPC response")
    else:
        # only error is not None
        response['error'] = str(error)

    return json.dumps(response)


class InternalRPCServer:
    chain = None

    def __init__(self,
                 chain: AsyncChainAPI,
                 event_bus: EndpointAPI = None,
                 debug_mode=False) -> None:
        self.event_bus = event_bus
        self.chain = chain
        self.logger: ExtendedDebugLogger = get_logger('veda.services.components.syncer.internal_rpc.InternalRPCServer')
        self.debug_mode = debug_mode

    def validate_block_params(self, block_params: SyncBlockModel) -> None:
        if block_params.blockNumber < 0:
            raise ValidationError(
                f"Invalid block number: {block_params.blockNumber}"
            )

        if block_params.timestamp < 0:
            raise ValidationError(
                f"Invalid timestamp: {block_params.timestamp}"
            )

        # blockHash must be 32bytes
        if len(decode_hex(block_params.blockHash)) != 32:
            raise ValidationError(
                f"Invalid block hash: {block_params.blockHash}"
            )

    async def _handle_sync(self, params):
        self.event_bus.broadcast_nowait(
            NewBlockImportStarted(
                int(time.time())
            ),
            FIRE_AND_FORGET_BROADCASTING,
        )

        try:
            block_params: SyncBlockModel = SyncBlockModel.model_validate(params[0])
            transactions = params[1]

            self.validate_block_params(block_params)

            self.logger.debug("Syncing block %s", block_params.blockNumber)

            chain = cast(VedaAsyncChain, self.chain)
            vm = chain.get_vm()
            vm_header = vm.get_header()
            block_max_gas = vm_header.gas_limit
            # 检查新的 header 是不是当前 header 的下一块
            block_number = block_params.blockNumber
            applying_transactions = []

            # 检查 block header 合法性
            if block_number != vm_header.block_number:
                raise ValidationError(
                    f"This VM instance must only work on block #{vm_header}, "  # noqa: E501
                    f"but the target header has block #{block_number}"
                )

            block_hash = decode_hex(block_params.blockHash)
            if len(block_hash) != 32:
                raise ValidationError(
                    f"Invalid block hash: {block_params.blockHash}"
                )

            mix_hash = decode_hex(block_params.mixHash)
            if len(mix_hash) != 32:
                raise ValidationError(
                    f"Invalid mix hash: {block_params.blockHash}"
                )

            # 检查每笔 transaction 的合法性

            for transaction_idx, transaction in enumerate(transactions):
                tx = SyncTransactionModel.model_validate(transaction)

                sender = decode_hex(tx.sender)
                if len(sender) != 20:
                    raise ValidationError(
                        f"Invalid sender address: {tx.sender}"
                    )

                try:
                    data = decode_hex(tx.data)
                except Exception as e:
                    self.logger.error("Invalid transaction data:, idx: %s, sender: %s", transaction_idx, tx.sender)
                    continue

                tx_hash = decode_hex(tx.txHash)
                if len(tx_hash) != 32:
                    raise ValidationError(
                        f"Invalid tx hash: {tx.txHash}"
                    )

                address_to = decode_hex(tx.to)

                vm_tx = VedaTransaction(nonce=tx.nonce,
                                            veda_sender=sender,
                                            gas=block_max_gas,
                                            to=address_to,
                                            data=data,
                                            veda_txhash=tx_hash)

                applying_transactions.append(vm_tx)

            applying_transactions_tuple = tuple(applying_transactions)

            new_block, _receipts, _computations = chain.apply_transactions(applying_transactions_tuple)

            mined_block = chain.mine_block(
                mix_hash=mix_hash,
                timestamp=block_params.timestamp,
                veda_block_hash=block_hash,
                veda_block_number=block_params.blockNumber,
                veda_timestamp=block_params.timestamp,
            )

            self.logger.debug(
                "%s contains %d transactions, %d succeeded, veda blockHash: %s",  # noqa: E501
                mined_block,
                len(mined_block.transactions),
                len(_receipts),
                block_params.blockHash
            )

            # 导入完成以后，广播新块已成功导入事件、数据库解锁事件
            self.event_bus.broadcast_nowait(
                NewBlockImportFinished(
                    int(time.time())
                ),
                FIRE_AND_FORGET_BROADCASTING,
            )
        except Exception as e:
            self.event_bus.broadcast_nowait(
                NewBlockImportCanceled(
                    int(time.time()),
                    str(e)
                ),
                FIRE_AND_FORGET_BROADCASTING,
            )

            raise e

    async def _handle_get_latest_block(self, params):
        chain = cast(VedaAsyncChain, self.chain)

        header = cast(VedaBlockHeader, chain.get_canonical_head())
        data = {
            'veda_block_hash': encode_hex(header.veda_block_hash),
            'veda_block_number': header.veda_block_number,
            'veda_timestamp': header.veda_timestamp,
        }

        return data


    async def _handle_batch_transactions(self,
                          request: Dict[str, Any]) -> Tuple[Any, Union[Exception, str, None]]:
        """
        :returns: (result, error) - result is None if error is provided. Error must be
            convertable to string with ``str(error)``.
        """
        try:
            validate_request(request)

            if request.get('jsonrpc', None) != '2.0':
                raise NotImplementedError("Only the 2.0 jsonrpc protocol is supported")

            method = request['method']
            params = request.get('params', [])

            if method == 'sync':
                result = await self._handle_sync(params)
            elif method == 'get_latest_block':
                result = await self._handle_get_latest_block(params)
            else:
                raise NotImplementedError('Only ["sync", "get_latest_block"] method is supported')

        except TypeError as exc:
            error = f"Invalid parameters. Check parameter count and types. {exc}"
            if self.debug_mode:
                raise
            return None, error
        except NotImplementedError as exc:
            error = "Method not implemented: %r %s" % (request['method'], exc)
            if self.debug_mode:
                raise
            return None, error
        except ValidationError as exc:
            self.logger.debug("Validation error while executing RPC method", exc_info=True)
            if self.debug_mode:
                raise
            return None, exc
        except pydantic.ValidationError as exc:
            self.logger.debug("Validation error while executing RPC method", exc_info=True)
            if self.debug_mode:
                raise
            return None, exc
        except Exception as exc:
            self.logger.warning("RPC method caused exception", exc_info=True)
            if self.debug_mode:
                raise
            return None, exc
        else:
            return result, None

    async def execute(self,
                      request: Dict[str, Any]) -> str:
        result, error = await self._handle_batch_transactions(request)
        return generate_response(request, result, error)