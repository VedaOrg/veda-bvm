import requests

def generate_request(block_hash, block_number, timestamp, transactions):
    data = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "sync",
        "params": [
            {
                "blockHash": block_hash,
                "blockNumber": block_number,
                "timestamp": timestamp,
                "mixHash": '00' * 31 + '6f',  # the 'identity' precompile
            },
            transactions
        ]
    }

    return data

def request(data):
    url = 'http://127.0.0.1:8679'
    print(requests.post(url, json=data).content)