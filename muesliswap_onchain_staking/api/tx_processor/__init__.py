import peewee
import pycardano
from ..db_models import Block, TransactionOutput
from ..util import FixedTxHashTransaction

from .staking import process_tx as process_staking_tx
from .farms import process_tx as process_farms_tx


def process_tx(
    tx: FixedTxHashTransaction,
    block: Block,
    block_index: int,
    # tracked_gov_states: TrackedGovStates,
    # tracked_treasury_states: TrackedTreasuryStates,
):
    """
    Process a transaction and update the database accordingly.
    """

    # mark all inputs to the transaction as spent
    spent_inputs = [
        (_input.transaction_id.payload.hex(), _input.index)
        for _, _input in enumerate(tx.transaction_body.inputs)
    ]
    for h, i in spent_inputs:
        TransactionOutput.update(spent_in_block=block).where(
            (TransactionOutput.transaction_hash == h) & (TransactionOutput.output_index == i)
        ).execute()

    # model specific processing
    process_farms_tx(tx, block, block_index)
    process_staking_tx(tx, block, block_index)
