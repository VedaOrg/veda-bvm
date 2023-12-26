Veda BVM
======

BVM is still in very rapid iterations before the 1.0.0 release, and the code may be updated at any time. Please try to keep it consistent with the master branch.

## Setup BVM instance
We recommend to use docker to deploy the BVM.

```bash
docker-compose up -d
```

## Exposed Ports
| Port | Description                        | External Service |
|------|------------------------------------|------------------|
| 8545 | Veda RPC HTTP Sevice               | ✓                |
| 8679 | Internal RPC Service for veda-core | ✗                |

Since no authentication for internal RPC, **NEVER EXPOSE 8679 PORT TO PUBLIC NETWORK**, make sure the firewall set correctly.

## Simple Test

Simple tests locate in `scripts/tests` directory, you can run it by:

* `scripts/tests/testinternalrpc.py`: Fast and simple test for interaction with internal RPC service.
* `scripts/tests/testrpc.py`: Fast and simple test for interaction with external RPC service.
* `scripts/tests/internal_rpc_test/vbtc.py`: Simple test for deploy a VRC20 token contract.

## Acknowledgments

Thanks for the following projects:
- py-ethereum
- trinity