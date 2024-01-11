from typing import (
    Any,
    Dict,
    List,
)

from lahja import EndpointAPI
from eth_utils import (
    decode_hex,
    encode_hex,
)

from veda.abc import (
    BlockAPI,
    SignedTransactionAPI,
    ComputationAPI,
)
from veda.constants import (
    GENESIS_BLOCK_NUMBER,
)
from veda.exceptions import (
    TransactionNotFound,
)
from veda.rpc.base import AsyncChainAPI
from veda.config import VedaConfig
from veda.rpc.exceptions import RpcError
from veda.rpc.format import (
    format_params,
)
from veda.rpc.modules.base import (
    Eth1ChainRPCModule,
)


def transaction_trace_result(computation: 'ComputationAPI', block: BlockAPI, transaction: SignedTransactionAPI,
                             transaction_idx: int, call_trace: List[int], result: List) -> List[Dict[str, Any]]:
    # Append transaction to result
    data = {
        "action": {
            "from": encode_hex(transaction.sender),
            "gas": hex(transaction.gas),
            "value": hex(0)  # fix value to 0
        },
        "blockHash": encode_hex(block.hash),
        "blockNumber": block.number,
        "result": {
            "gasUsed": hex(computation.get_gas_used()),
        },
        # equals to children computations
        "subtraces": len(computation.children),
        "traceAddress": call_trace,
        "transactionHash": encode_hex(transaction.hash),
        "transactionPosition": transaction_idx,
        "type": "create" if computation.msg.is_create else "call"
    }

    if computation.msg.is_create:
        data["action"]["init"] = encode_hex(transaction.data)
        data["result"]["code"] = encode_hex(computation.output)
        data["result"]["address"] = encode_hex(computation.msg.storage_address)
    else:
        data["action"]["callType"] = computation.call_type.lower()
        data["action"]["input"] = encode_hex(transaction.data)
        data["action"]["to"] = encode_hex(transaction.to)
        data["result"]["output"] = encode_hex(computation.output)

    if computation.is_error:
        computation.error.__str__()

    result.append(data)

    if call_trace is []:
        call_trace = [0]

    # Recursively append child transactions to result
    for idx, child in enumerate(computation.children):
        transaction_trace_result(child, block, transaction, transaction_idx, call_trace + [idx], result)

    return result


class Trace(Eth1ChainRPCModule):
    """
    All the methods defined by JSON-RPC API, starting with "eth_"...

    Any attribute without an underscore is publicly accessible.
    """

    def __init__(self,
                 chain: AsyncChainAPI,
                 event_bus: EndpointAPI,
                 veda_config: VedaConfig) -> None:
        self.veda_config = veda_config
        self.chain = chain
        self.event_bus = event_bus
        super().__init__(chain, event_bus)

    @format_params(decode_hex)
    async def transaction(self, transaction_hash):

        # Get block number of transaction
        try:
            block_number, tx_index = await self.chain.coro_get_canonical_transaction_index(
                transaction_hash,
            )
        except TransactionNotFound as exc:
            raise RpcError(
                f"Transaction {encode_hex(transaction_hash)} is not in the canonical chain"
            ) from exc

        if block_number <= GENESIS_BLOCK_NUMBER:
            raise Exception(f"No transaction in genesis or less than {GENESIS_BLOCK_NUMBER}")

        block = await self.chain.coro_get_canonical_block_by_number(block_number)

        if block is None:
            raise Exception(f"Block {block_number} not found")

        # Access the parent block
        parent_block = await self.chain.coro_get_canonical_block_by_number(block_number - 1)
        if parent_block is None:
            raise Exception(f"Parent block not found for block {block_number}")

        vm = self.chain.get_vm(parent_block.header)

        with vm.in_costless_state() as state:
            for idx, tx in enumerate(block.transactions):

                # Apply transaction to state
                computation = state.apply_transaction(tx)

                # Process transaction
                if idx == tx_index:
                    # Retrieve transaction and state at this index
                    result = []
                    trace = transaction_trace_result(computation, parent_block, tx, idx, [], result)
                    return trace
