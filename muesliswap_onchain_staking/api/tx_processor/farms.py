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
from ..config import vote_permission_nft_policy_id
from ..db_models import Block, TransactionOutput
from ..db_models import (
    StakingState,
)

# from ...onchain.staking import staking as onchain_staking

import logging

from ..db_models.staking import (
    StakingParams,
    StakingState,
)
from ...utils.from_script_context import from_address

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