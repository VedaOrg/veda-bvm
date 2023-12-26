import requests

def internal_get_block():
    jsonrpc_payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "get_latest_block",
        "params": []
    }

    ret = requests.post('http://127.0.0.1:8679/', json=jsonrpc_payload).json()
    return ret

def internal_rpc_simple(veda_block_number):
    jsonrpc_payload = {
      "id": 1,
      "jsonrpc": "2.0",
      "method": "sync",
      "params": [
        {
          "blockHash": '0x' + '00' * 31 + '1f',  # the 'identity' precompile
          "blockNumber": veda_block_number + 1,
          'mixHash': '00' * 31 + '6f',  # the 'identity' precompile
          "timestamp": 123123123123
        },
        [
            {
                'to': '0xe0E09f974F6B8C35a9c73fbbC3433F7ef83e4d09',  # the 'identity' precompile
                'sender': '0x' + '00' * 19 + '04',  # the 'identity' precompile
                'nonce': 0,
                'txHash': '0x' + '00' * 31 + '04',  # the 'identity' precompile
                'data': '0x123456',
            }
        ]
      ]
    }

    print(requests.post('http://127.0.0.1:8679/', json=jsonrpc_payload).json())

def get_block_by_num():
    jsonrpc_payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "eth_getBlockByNumber",
        "params": [
            822269,
            False
        ]
    }

    print(requests.post('http://127.0.0.1:8545/', json=jsonrpc_payload).json())


if __name__ == '__main__':
    ret = internal_get_block()
    print(ret)
    veda_block_number = ret['result']['veda_block_number']
    print('veda_block_number', veda_block_number)
    internal_rpc_simple(veda_block_number)
    get_block_by_num()
