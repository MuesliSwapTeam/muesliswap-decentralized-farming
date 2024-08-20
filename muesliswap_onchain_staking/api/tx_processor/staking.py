import pycardano

from .to_db import (
    add_output,
    add_address,
    add_datum,
    add_token_token,
    add_token,
    add_transaction,
    to_datetime,
)
from ...utils.from_script_context import from_address
from ..db_models import Block, TransactionOutput
from muesliswap_onchain_staking.api.db_models import staking as db_staking
from muesliswap_onchain_staking.onchain import staking_types as onchain_staking_types
from muesliswap_onchain_staking.api.config import (
    staking_address,
)
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
    for i, output in enumerate(tx.transaction_body.outputs):
        if output.address.to_primitive() == staking_address:
            _LOGGER.info(f"Staking transaction: {tx.id.payload.hex()}")
        staking_output = add_output(
            output,
            i,
            tx.id.payload.hex(),
            block,
            block_index,
        )
        try:
            onchain_staking_state: onchain_staking_types.StakingPosition = (
                onchain_staking_types.StakingPosition.from_primitive(output.datum.data)
            )
        except Exception:
            _LOGGER.info(f"Invalid staking position datum at {tx.id.payload.hex()}")
            continue

        utxo_assets = {}
        for sh, assets in output.amount.multi_asset.items():
            for an, amount in assets.items():
                utxo_assets[f"{str(sh)}.{str(an)}"] = amount
        utxo_assets["lovelace"] = output.amount.coin

        db_staking_params = db_staking.StakingParams.get_or_create(
            owner = add_address(from_address(onchain_staking_state.owner)),
            pool_id = onchain_staking_state.pool_id.payload.hex(),
            staked_since = to_datetime(onchain_staking_state.staked_since),
            batching_output_index = onchain_staking_state.batching_output_index,
        )[0]
        for i, cumulative_pool_rpt in enumerate(onchain_staking_state.cumulative_pool_rpts_at_start):
            db_staking.StakingCumulativePoolRptsAtStart.get_or_create(
                staking_params = db_staking_params,
                cumulative_pool_rpts_at_start_numerator = cumulative_pool_rpt.numerator,
                cumulative_pool_rpts_at_start_denominator = cumulative_pool_rpt.denominator,
                index = i,
            )
        _db_staking_state = db_staking.StakingState.create(
            transaction_output=staking_output,
            staking_params=db_staking_params,
        )