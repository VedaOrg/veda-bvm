import json
from pathlib import Path

import sha3

from veda.db import get_db_backend
from lahja import AsyncioEndpoint, ConnectionConfig

from eth_utils import (
    to_hex,
)

import asyncio
from typing import Union

import uvicorn
from fastapi import FastAPI, Response
from jsonrpcobjects.objects import (
    ErrorResponse,
    Notification,
    ParamsNotification,
    ParamsRequest,
    Request,
    ResultResponse,
)

from veda.db.backends.level import LevelDB
from veda.rpc.chain import VedaAsyncChain
from veda.config import VedaConfig
from veda.constants import MAIN_EVENTBUS_ENDPOINT
from veda.rpc.modules import initialize_veda_modules
from veda.rpc.server import RPCServer

app = FastAPI()
RequestType = Union[ParamsRequest, Request, ParamsNotification, Notification]
connection_config = ConnectionConfig.from_name(
    MAIN_EVENTBUS_ENDPOINT,
    Path('/tmp/ipcdir')
)
event_bus = AsyncioEndpoint('event_bus')
base_db = LevelDB(db_path="/tmp/mydb.db")
chain = VedaAsyncChain(base_db=base_db)
config = VedaConfig(genesis_config={})
rpc = RPCServer(initialize_veda_modules(chain, event_bus, config), chain, event_bus)

@app.post("/", response_model=Union[ErrorResponse, ResultResponse, None])
async def http_process_rpc(request: RequestType) -> Response:
    """Process RPC request through HTTP server."""

    transaction = request.model_dump()


    json_rpc_response = await rpc.execute_with_access_control([], transaction)
    # json_rpc_response = await rpc.process_request_async(request.model_dump_json())
    return Response(content=json_rpc_response, media_type="application/json")

async def background_coroutine():
    while True:
        print("background process running...")
        await asyncio.sleep(5)  # 在这里执行后台任务，每隔5秒运行一次


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_coroutine())

def _run():
    import random
    def build_request(method, params):
        return {"jsonrpc": "2.0", "method": method, "params": params, "id": random.randrange(1000)}

    def result_from_response(response_str):
        response = json.loads(response_str)
        return (response.get('result', None), response.get('error', None))

    # ------ BalanceOf ------
    function_name = "balanceOf"
    SENDER_ADDRESS = b'P\x96\x95\x07\t\xf0\x08R!\x84|\x16\x18\xae\xd1\xfaJ\xb9\xe1\xda'
    target_address = SENDER_ADDRESS.rjust(32, b"\x00")
    function_signature = f"{function_name}(address)"

    function_selector = sha3.keccak_256(function_signature.encode('utf-8')).digest()[:4]
    function_parameter = target_address
    function_call_data = function_selector + function_parameter

    transaction = {
        'from': '0x' + 'ff' * 20,  # unfunded address
        'to': '0xe0E09f974F6B8C35a9c73fbbC3433F7ef83e4d09',
        'gasPrice': '0',
        'gas': '0x61a8',
        'data': to_hex(function_call_data),
    }

    transaction.update({
        'veda_sender': '0x' + 'ff' * 20,  # unfunded address
    })

    request = build_request('eth_call', [transaction, 'latest'])

    response = asyncio.get_event_loop().run_until_complete(rpc.execute_with_access_control([], request))
    result, error = result_from_response(response)

    print(result)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9090)