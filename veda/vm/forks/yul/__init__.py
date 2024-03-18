from typing import Sequence, Tuple

import eth_utils
from eth_utils import ValidationError
from veda.vm.interrupt import EVMMissingData

from veda.abc import SignedTransactionAPI, BlockHeaderAPI, ReceiptAPI, ComputationAPI
from veda.vm.forks.veda import VedaVM


class YulVM(VedaVM):
    fork = 'yul'

    def apply_all_transactions(self, transactions: Sequence[SignedTransactionAPI], base_header: BlockHeaderAPI) -> \
    Tuple[BlockHeaderAPI, Tuple[SignedTransactionAPI, ...], Tuple[ReceiptAPI, ...], Tuple[ComputationAPI, ...]]:

        vm_header = self.get_header()
        if base_header.block_number != vm_header.block_number:
            raise ValidationError(
                f"This VM instance must only work on block #{self.get_header().block_number}, "  # noqa: E501
                f"but the target header has block #{base_header.block_number}"
            )

        receipts = []
        computations = []
        applied_transactions = []
        previous_header = base_header
        result_header = base_header


        # Reorder transactions:
        # Traverse the original transactions list, create a new transaction list where the execution order of transactions needs to meet the following requirements:
        #   1. Transactions are grouped by account, and the order between the groups is determined by the position of the smallest nonce of each account in the original transaction list.
        #   2. Transactions within the group are sorted by nonce's order.

        grouped_transactions = {}
        for i, tx in enumerate(transactions):
            from_address = tx.sender
            if from_address not in grouped_transactions:
                grouped_transactions[from_address] = {'transactions': [tx], 'min_nonce_index': i}
            else:
                grouped_transactions[from_address]['transactions'].append(tx)
                # Update min_nonce_index if the current tx has a smaller nonce
                if tx.nonce < transactions[grouped_transactions[from_address]['min_nonce_index']].nonce:
                    grouped_transactions[from_address]['min_nonce_index'] = i

        # Sort groups by min_nonce_index
        sorted_groups = sorted(grouped_transactions.values(), key=lambda x: x['min_nonce_index'])

        # Sort transactions within each group by nonce
        sorted_transactions = []
        for group in sorted_groups:
            sorted_transactions.extend(sorted(group['transactions'], key=lambda x: x.nonce))


        for transaction_index, transaction in enumerate(sorted_transactions):
            snapshot = self.state.snapshot()
            try:
                receipt, computation = self.apply_transaction(
                    previous_header,
                    transaction,
                )
            except eth_utils.ValidationError as e:
                # A validation exception usually is raised before VM execution.
                self.logger.debug('Transaction %s raise an validation error, reason: %s', transaction.hash, e)
                continue
            except EVMMissingData:
                self.state.revert(snapshot)
                raise

            result_header = self.add_receipt_to_header(previous_header, receipt)
            previous_header = result_header
            receipts.append(receipt)
            computations.append(computation)
            applied_transactions.append(transaction)

            self.transaction_applied_hook(
                transaction_index,
                transactions,
                vm_header,
                result_header,
                computation,
                receipt,
            )

        receipts_tuple = tuple(receipts)
        computations_tuple = tuple(computations)
        applied_transactions_tuple = tuple(applied_transactions)

        return result_header, applied_transactions_tuple, receipts_tuple, computations_tuple

