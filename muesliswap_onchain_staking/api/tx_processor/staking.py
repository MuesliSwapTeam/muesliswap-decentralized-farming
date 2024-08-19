import pycardano

from opshin.ledger.api_v2 import FinitePOSIXTime
from . import from_db
from .to_db import (
    add_output,
    add_address,
    add_datum,
    add_token_token,
    add_token,
    add_transaction,
)
from ..db_models import Block, TransactionOutput
import logging

_LOGGER = logging.getLogger(__name__)


def process_tx(
    tx: pycardano.Transaction,
    block: Block,
    block_index: int,
):
    """
    Process a transaction and update the database accordingly.
    """
    pass