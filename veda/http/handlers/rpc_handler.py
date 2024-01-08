import logging
from typing import (
    Any,
    Callable,
    Dict,
)

from aiohttp import web
from eth_utils.toolz import curry

from veda.http.exceptions import JsonParsingException, JsonRpcCallException
from veda.http.handlers.base import BaseHTTPHandler, response_error


#
# JSON-RPC
#


async def load_json_request(request: web.Request) -> Any:
    try:
        body_json = await request.json()
    except Exception:
        raise JsonParsingException(f"Invalid request: {request}")
    else:
        return body_json


async def execute_json_rpc(
    execute_rpc: Callable[[Any], Any],
    json_request: Dict['str', Any]
) -> str:
    try:
        result = await execute_rpc(json_request)
    except Exception as e:
        msg = f"Unrecognized exception while executing RPC: {e}"
        raise JsonRpcCallException(msg)
    else:
        return result

def cors_response(content_type='application/json', text='', status=200) -> web.Response:
    """
    Helper function to create a response with CORS headers.
    """
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, GET',
        'Access-Control-Allow-Headers': 'Content-Type',
    }
    return web.Response(content_type=content_type, text=text, headers=headers, status=status)


class RPCHandler(BaseHTTPHandler):

    @staticmethod
    @curry
    async def handle(execute_rpc: Callable[[Any], Any], request: web.Request) -> web.Response:
        logger = logging.getLogger('veda.http.handlers.rpc_handler')

        if request.method == 'OPTIONS':
            return cors_response()

        if request.method == 'POST':
            logger.debug('Receiving POST request: %s', request.path)
            try:
                body_json = await load_json_request(request)
            except JsonParsingException as e:
                return response_error('Bad request')

            try:
                result = await execute_json_rpc(execute_rpc, body_json)
            except JsonRpcCallException as e:
                return response_error(str(e))
            else:
                return cors_response(text=result)
        else:
            return response_error(f"Server doesn't support {request.method} request")
