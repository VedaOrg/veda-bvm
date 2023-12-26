from web3 import Web3
from eth_utils import encode_hex
import veda_internal_rpc

abi = [
	{
		"inputs": [
			{
				"internalType": "string",
				"name": "tokenName",
				"type": "string"
			},
			{
				"internalType": "string",
				"name": "tokenSymbol",
				"type": "string"
			},
			{
				"internalType": "uint256",
				"name": "supply",
				"type": "uint256"
			},
			{
				"internalType": "address",
				"name": "initialOwner",
				"type": "address"
			}
		],
		"stateMutability": "nonpayable",
		"type": "constructor"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "spender",
				"type": "address"
			},
			{
				"internalType": "uint256",
				"name": "allowance",
				"type": "uint256"
			},
			{
				"internalType": "uint256",
				"name": "needed",
				"type": "uint256"
			}
		],
		"name": "ERC20InsufficientAllowance",
		"type": "error"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "sender",
				"type": "address"
			},
			{
				"internalType": "uint256",
				"name": "balance",
				"type": "uint256"
			},
			{
				"internalType": "uint256",
				"name": "needed",
				"type": "uint256"
			}
		],
		"name": "ERC20InsufficientBalance",
		"type": "error"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "approver",
				"type": "address"
			}
		],
		"name": "ERC20InvalidApprover",
		"type": "error"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "receiver",
				"type": "address"
			}
		],
		"name": "ERC20InvalidReceiver",
		"type": "error"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "sender",
				"type": "address"
			}
		],
		"name": "ERC20InvalidSender",
		"type": "error"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "spender",
				"type": "address"
			}
		],
		"name": "ERC20InvalidSpender",
		"type": "error"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "owner",
				"type": "address"
			}
		],
		"name": "OwnableInvalidOwner",
		"type": "error"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "account",
				"type": "address"
			}
		],
		"name": "OwnableUnauthorizedAccount",
		"type": "error"
	},
	{
		"anonymous": False,
		"inputs": [
			{
				"indexed": True,
				"internalType": "address",
				"name": "owner",
				"type": "address"
			},
			{
				"indexed": True,
				"internalType": "address",
				"name": "spender",
				"type": "address"
			},
			{
				"indexed": False,
				"internalType": "uint256",
				"name": "value",
				"type": "uint256"
			}
		],
		"name": "Approval",
		"type": "event"
	},
	{
		"anonymous": False,
		"inputs": [
			{
				"indexed": True,
				"internalType": "address",
				"name": "previousOwner",
				"type": "address"
			},
			{
				"indexed": True,
				"internalType": "address",
				"name": "newOwner",
				"type": "address"
			}
		],
		"name": "OwnershipTransferred",
		"type": "event"
	},
	{
		"anonymous": False,
		"inputs": [
			{
				"indexed": True,
				"internalType": "address",
				"name": "from",
				"type": "address"
			},
			{
				"indexed": True,
				"internalType": "address",
				"name": "to",
				"type": "address"
			},
			{
				"indexed": False,
				"internalType": "uint256",
				"name": "value",
				"type": "uint256"
			}
		],
		"name": "Transfer",
		"type": "event"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "owner",
				"type": "address"
			},
			{
				"internalType": "address",
				"name": "spender",
				"type": "address"
			}
		],
		"name": "allowance",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "spender",
				"type": "address"
			},
			{
				"internalType": "uint256",
				"name": "value",
				"type": "uint256"
			}
		],
		"name": "approve",
		"outputs": [
			{
				"internalType": "bool",
				"name": "",
				"type": "bool"
			}
		],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "account",
				"type": "address"
			}
		],
		"name": "balanceOf",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "uint256",
				"name": "value",
				"type": "uint256"
			}
		],
		"name": "burn",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "account",
				"type": "address"
			},
			{
				"internalType": "uint256",
				"name": "value",
				"type": "uint256"
			}
		],
		"name": "burnFrom",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "decimals",
		"outputs": [
			{
				"internalType": "uint8",
				"name": "",
				"type": "uint8"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "to",
				"type": "address"
			},
			{
				"internalType": "uint256",
				"name": "amount",
				"type": "uint256"
			}
		],
		"name": "mint",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "name",
		"outputs": [
			{
				"internalType": "string",
				"name": "",
				"type": "string"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "owner",
		"outputs": [
			{
				"internalType": "address",
				"name": "",
				"type": "address"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "renounceOwnership",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "symbol",
		"outputs": [
			{
				"internalType": "string",
				"name": "",
				"type": "string"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "totalSupply",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "to",
				"type": "address"
			},
			{
				"internalType": "uint256",
				"name": "value",
				"type": "uint256"
			}
		],
		"name": "transfer",
		"outputs": [
			{
				"internalType": "bool",
				"name": "",
				"type": "bool"
			}
		],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "from",
				"type": "address"
			},
			{
				"internalType": "address",
				"name": "to",
				"type": "address"
			},
			{
				"internalType": "uint256",
				"name": "value",
				"type": "uint256"
			}
		],
		"name": "transferFrom",
		"outputs": [
			{
				"internalType": "bool",
				"name": "",
				"type": "bool"
			}
		],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "newOwner",
				"type": "address"
			}
		],
		"name": "transferOwnership",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	}
]

if __name__ == '__main__':
	bytecode = '608060405234801562000010575f80fd5b5060405162001dc738038062001dc783398181016040528101906200003691906200068f565b80848481600390816200004a91906200096a565b5080600490816200005c91906200096a565b5050505f73ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff1603620000d2575f6040517f1e4fbdf7000000000000000000000000000000000000000000000000000000008152600401620000c9919062000a5f565b60405180910390fd5b620000e3816200010060201b60201c565b50620000f63383620001c360201b60201c565b5050505062000b48565b5f60055f9054906101000a900473ffffffffffffffffffffffffffffffffffffffff1690508160055f6101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff1602179055508173ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff167f8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e060405160405180910390a35050565b5f73ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff160362000236575f6040517fec442f050000000000000000000000000000000000000000000000000000000081526004016200022d919062000a5f565b60405180910390fd5b620002495f83836200024d60201b60201c565b5050565b5f73ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff1603620002a1578060025f82825462000294919062000aa7565b9250508190555062000372565b5f805f8573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020015f20549050818110156200032d578381836040517fe450d38c000000000000000000000000000000000000000000000000000000008152600401620003249392919062000af2565b60405180910390fd5b8181035f808673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020015f2081905550505b5f73ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff1603620003bb578060025f828254039250508190555062000405565b805f808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020015f205f82825401925050819055505b8173ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef8360405162000464919062000b2d565b60405180910390a3505050565b5f604051905090565b5f80fd5b5f80fd5b5f80fd5b5f80fd5b5f601f19601f8301169050919050565b7f4e487b71000000000000000000000000000000000000000000000000000000005f52604160045260245ffd5b620004d2826200048a565b810181811067ffffffffffffffff82111715620004f457620004f36200049a565b5b80604052505050565b5f6200050862000471565b9050620005168282620004c7565b919050565b5f67ffffffffffffffff8211156200053857620005376200049a565b5b62000543826200048a565b9050602081019050919050565b5f5b838110156200056f57808201518184015260208101905062000552565b5f8484015250505050565b5f620005906200058a846200051b565b620004fd565b905082815260208101848484011115620005af57620005ae62000486565b5b620005bc84828562000550565b509392505050565b5f82601f830112620005db57620005da62000482565b5b8151620005ed8482602086016200057a565b91505092915050565b5f819050919050565b6200060a81620005f6565b811462000615575f80fd5b50565b5f815190506200062881620005ff565b92915050565b5f73ffffffffffffffffffffffffffffffffffffffff82169050919050565b5f62000659826200062e565b9050919050565b6200066b816200064d565b811462000676575f80fd5b50565b5f81519050620006898162000660565b92915050565b5f805f8060808587031215620006aa57620006a96200047a565b5b5f85015167ffffffffffffffff811115620006ca57620006c96200047e565b5b620006d887828801620005c4565b945050602085015167ffffffffffffffff811115620006fc57620006fb6200047e565b5b6200070a87828801620005c4565b93505060406200071d8782880162000618565b9250506060620007308782880162000679565b91505092959194509250565b5f81519050919050565b7f4e487b71000000000000000000000000000000000000000000000000000000005f52602260045260245ffd5b5f60028204905060018216806200078b57607f821691505b602082108103620007a157620007a062000746565b5b50919050565b5f819050815f5260205f209050919050565b5f6020601f8301049050919050565b5f82821b905092915050565b5f60088302620008057fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff82620007c8565b620008118683620007c8565b95508019841693508086168417925050509392505050565b5f819050919050565b5f620008526200084c6200084684620005f6565b62000829565b620005f6565b9050919050565b5f819050919050565b6200086d8362000832565b620008856200087c8262000859565b848454620007d4565b825550505050565b5f90565b6200089b6200088d565b620008a881848462000862565b505050565b5b81811015620008cf57620008c35f8262000891565b600181019050620008ae565b5050565b601f8211156200091e57620008e881620007a7565b620008f384620007b9565b8101602085101562000903578190505b6200091b6200091285620007b9565b830182620008ad565b50505b505050565b5f82821c905092915050565b5f620009405f198460080262000923565b1980831691505092915050565b5f6200095a83836200092f565b9150826002028217905092915050565b62000975826200073c565b67ffffffffffffffff8111156200099157620009906200049a565b5b6200099d825462000773565b620009aa828285620008d3565b5f60209050601f831160018114620009e0575f8415620009cb578287015190505b620009d785826200094d565b86555062000a46565b601f198416620009f086620007a7565b5f5b8281101562000a1957848901518255600182019150602085019450602081019050620009f2565b8683101562000a39578489015162000a35601f8916826200092f565b8355505b6001600288020188555050505b505050505050565b62000a59816200064d565b82525050565b5f60208201905062000a745f83018462000a4e565b92915050565b7f4e487b71000000000000000000000000000000000000000000000000000000005f52601160045260245ffd5b5f62000ab382620005f6565b915062000ac083620005f6565b925082820190508082111562000adb5762000ada62000a7a565b5b92915050565b62000aec81620005f6565b82525050565b5f60608201905062000b075f83018662000a4e565b62000b16602083018562000ae1565b62000b25604083018462000ae1565b949350505050565b5f60208201905062000b425f83018462000ae1565b92915050565b6112718062000b565f395ff3fe608060405234801561000f575f80fd5b50600436106100f3575f3560e01c806370a082311161009557806395d89b411161006457806395d89b411461025d578063a9059cbb1461027b578063dd62ed3e146102ab578063f2fde38b146102db576100f3565b806370a08231146101e9578063715018a61461021957806379cc6790146102235780638da5cb5b1461023f576100f3565b806323b872dd116100d157806323b872dd14610163578063313ce5671461019357806340c10f19146101b157806342966c68146101cd576100f3565b806306fdde03146100f7578063095ea7b31461011557806318160ddd14610145575b5f80fd5b6100ff6102f7565b60405161010c9190610ebf565b60405180910390f35b61012f600480360381019061012a9190610f70565b610387565b60405161013c9190610fc8565b60405180910390f35b61014d6103a9565b60405161015a9190610ff0565b60405180910390f35b61017d60048036038101906101789190611009565b6103b2565b60405161018a9190610fc8565b60405180910390f35b61019b6103e0565b6040516101a89190611074565b60405180910390f35b6101cb60048036038101906101c69190610f70565b6103e8565b005b6101e760048036038101906101e2919061108d565b6103fe565b005b61020360048036038101906101fe91906110b8565b610412565b6040516102109190610ff0565b60405180910390f35b610221610457565b005b61023d60048036038101906102389190610f70565b61046a565b005b61024761048a565b60405161025491906110f2565b60405180910390f35b6102656104b2565b6040516102729190610ebf565b60405180910390f35b61029560048036038101906102909190610f70565b610542565b6040516102a29190610fc8565b60405180910390f35b6102c560048036038101906102c0919061110b565b610564565b6040516102d29190610ff0565b60405180910390f35b6102f560048036038101906102f091906110b8565b6105e6565b005b60606003805461030690611176565b80601f016020809104026020016040519081016040528092919081815260200182805461033290611176565b801561037d5780601f106103545761010080835404028352916020019161037d565b820191905f5260205f20905b81548152906001019060200180831161036057829003601f168201915b5050505050905090565b5f8061039161066a565b905061039e818585610671565b600191505092915050565b5f600254905090565b5f806103bc61066a565b90506103c9858285610683565b6103d4858585610715565b60019150509392505050565b5f6012905090565b6103f0610805565b6103fa828261088c565b5050565b61040f61040961066a565b8261090b565b50565b5f805f8373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020015f20549050919050565b61045f610805565b6104685f61098a565b565b61047c8261047661066a565b83610683565b610486828261090b565b5050565b5f60055f9054906101000a900473ffffffffffffffffffffffffffffffffffffffff16905090565b6060600480546104c190611176565b80601f01602080910402602001604051908101604052809291908181526020018280546104ed90611176565b80156105385780601f1061050f57610100808354040283529160200191610538565b820191905f5260205f20905b81548152906001019060200180831161051b57829003601f168201915b5050505050905090565b5f8061054c61066a565b9050610559818585610715565b600191505092915050565b5f60015f8473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020015f205f8373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020015f2054905092915050565b6105ee610805565b5f73ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff160361065e575f6040517f1e4fbdf700000000000000000000000000000000000000000000000000000000815260040161065591906110f2565b60405180910390fd5b6106678161098a565b50565b5f33905090565b61067e8383836001610a4d565b505050565b5f61068e8484610564565b90507fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff811461070f5781811015610700578281836040517ffb8f41b20000000000000000000000000000000000000000000000000000000081526004016106f7939291906111a6565b60405180910390fd5b61070e84848484035f610a4d565b5b50505050565b5f73ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff1603610785575f6040517f96c6fd1e00000000000000000000000000000000000000000000000000000000815260040161077c91906110f2565b60405180910390fd5b5f73ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff16036107f5575f6040517fec442f050000000000000000000000000000000000000000000000000000000081526004016107ec91906110f2565b60405180910390fd5b610800838383610c1c565b505050565b61080d61066a565b73ffffffffffffffffffffffffffffffffffffffff1661082b61048a565b73ffffffffffffffffffffffffffffffffffffffff161461088a5761084e61066a565b6040517f118cdaa700000000000000000000000000000000000000000000000000000000815260040161088191906110f2565b60405180910390fd5b565b5f73ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff16036108fc575f6040517fec442f050000000000000000000000000000000000000000000000000000000081526004016108f391906110f2565b60405180910390fd5b6109075f8383610c1c565b5050565b5f73ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff160361097b575f6040517f96c6fd1e00000000000000000000000000000000000000000000000000000000815260040161097291906110f2565b60405180910390fd5b610986825f83610c1c565b5050565b5f60055f9054906101000a900473ffffffffffffffffffffffffffffffffffffffff1690508160055f6101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff1602179055508173ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff167f8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e060405160405180910390a35050565b5f73ffffffffffffffffffffffffffffffffffffffff168473ffffffffffffffffffffffffffffffffffffffff1603610abd575f6040517fe602df05000000000000000000000000000000000000000000000000000000008152600401610ab491906110f2565b60405180910390fd5b5f73ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff1603610b2d575f6040517f94280d62000000000000000000000000000000000000000000000000000000008152600401610b2491906110f2565b60405180910390fd5b8160015f8673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020015f205f8573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020015f20819055508015610c16578273ffffffffffffffffffffffffffffffffffffffff168473ffffffffffffffffffffffffffffffffffffffff167f8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b92584604051610c0d9190610ff0565b60405180910390a35b50505050565b5f73ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff1603610c6c578060025f828254610c609190611208565b92505081905550610d3a565b5f805f8573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020015f2054905081811015610cf5578381836040517fe450d38c000000000000000000000000000000000000000000000000000000008152600401610cec939291906111a6565b60405180910390fd5b8181035f808673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020015f2081905550505b5f73ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff1603610d81578060025f8282540392505081905550610dcb565b805f808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020015f205f82825401925050819055505b8173ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef83604051610e289190610ff0565b60405180910390a3505050565b5f81519050919050565b5f82825260208201905092915050565b5f5b83811015610e6c578082015181840152602081019050610e51565b5f8484015250505050565b5f601f19601f8301169050919050565b5f610e9182610e35565b610e9b8185610e3f565b9350610eab818560208601610e4f565b610eb481610e77565b840191505092915050565b5f6020820190508181035f830152610ed78184610e87565b905092915050565b5f80fd5b5f73ffffffffffffffffffffffffffffffffffffffff82169050919050565b5f610f0c82610ee3565b9050919050565b610f1c81610f02565b8114610f26575f80fd5b50565b5f81359050610f3781610f13565b92915050565b5f819050919050565b610f4f81610f3d565b8114610f59575f80fd5b50565b5f81359050610f6a81610f46565b92915050565b5f8060408385031215610f8657610f85610edf565b5b5f610f9385828601610f29565b9250506020610fa485828601610f5c565b9150509250929050565b5f8115159050919050565b610fc281610fae565b82525050565b5f602082019050610fdb5f830184610fb9565b92915050565b610fea81610f3d565b82525050565b5f6020820190506110035f830184610fe1565b92915050565b5f805f606084860312156110205761101f610edf565b5b5f61102d86828701610f29565b935050602061103e86828701610f29565b925050604061104f86828701610f5c565b9150509250925092565b5f60ff82169050919050565b61106e81611059565b82525050565b5f6020820190506110875f830184611065565b92915050565b5f602082840312156110a2576110a1610edf565b5b5f6110af84828501610f5c565b91505092915050565b5f602082840312156110cd576110cc610edf565b5b5f6110da84828501610f29565b91505092915050565b6110ec81610f02565b82525050565b5f6020820190506111055f8301846110e3565b92915050565b5f806040838503121561112157611120610edf565b5b5f61112e85828601610f29565b925050602061113f85828601610f29565b9150509250929050565b7f4e487b71000000000000000000000000000000000000000000000000000000005f52602260045260245ffd5b5f600282049050600182168061118d57607f821691505b6020821081036111a05761119f611149565b5b50919050565b5f6060820190506111b95f8301866110e3565b6111c66020830185610fe1565b6111d36040830184610fe1565b949350505050565b7f4e487b71000000000000000000000000000000000000000000000000000000005f52601160045260245ffd5b5f61121282610f3d565b915061121d83610f3d565b9250828201905080821115611235576112346111db565b5b9291505056fea2646970667358221220cf9f79de13326ffb15a8c9b3737e238eaec7c1a99fd7351c99ee2cdf961cf8c864736f6c63430008160033'

	w3 = Web3()

	contract = w3.eth.contract(abi=abi, bytecode=bytecode)
	args = [
			'Virtual Bitcoin',
			'VBTC',
			1000000000000000000,
			Web3.to_checksum_address('0x5096950709f0085221847c1618aed1fa4ab9e1da'),
	]
	# encode constructor arguments
	constructor_bytecode = contract.constructor(*args).data_in_transaction

	# Generate transaction json using web3
	transaction = {
		'sender': '0x5096950709f0085221847c1618aed1fa4ab9e1da',
		'nonce': 0,
		'txHash': encode_hex(b'\x00'*32),
		'to': '',
		'data': constructor_bytecode
	}

	block_hash = '0x' + '00' * 31 + '1f'
	block_number = 819000
	timestamp = 1
	request_data = veda_internal_rpc.generate_request(block_hash, block_number, timestamp, [
		transaction
	])


	print(veda_internal_rpc.request(request_data))