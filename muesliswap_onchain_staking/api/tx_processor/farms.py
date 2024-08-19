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
    to_datetime,
)
import logging

from muesliswap_onchain_staking.api.config import (
    farm_nft_policy_id,
)
from muesliswap_onchain_staking.onchain import staking as onchain_staking
from muesliswap_onchain_staking.onchain import staking_types as onchain_staking_types
from muesliswap_onchain_staking.api.db_models import farms as db_farms
from muesliswap_onchain_staking.api.db_models import Block, AssetName

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
        if not output.amount.multi_asset.get(farm_nft_policy_id):
            continue
        _LOGGER.info(f"Transaction contains farm nft {tx.id.payload.hex()}")
        farm_output = add_output(
            output,
            i,
            tx.id.payload.hex(),
            block,
            block_index,
        )
        try:
            onchain_farm_state: onchain_staking_types.FarmState = (
                onchain_staking_types.FarmState.from_primitive(output.datum.data)
            )
        except Exception:
            _LOGGER.info(f"Invalid farm state at {tx.id.payload.hex()}")
            continue
        farm_state_nft_name = list(
            output.amount.multi_asset[farm_nft_policy_id].keys()
        )[0]
        onchain_farm_state_params = onchain_farm_state.params

        utxo_assets = {}
        for sh, assets in output.amount.multi_asset.items():
            for an, amount in assets.items():
                utxo_assets[f"{str(sh)}.{str(an)}"] = amount
        utxo_assets["lovelace"] = output.amount.coin

        db_farm_state_params = db_farms.FarmParams.get_or_create(
            pool_id=farm_state_nft_name.payload.hex(),
            stake_token=add_token_token(onchain_farm_state_params.stake_token),
            farm_type=str(onchain_farm_state.farm_type),
            last_update_time=to_datetime(onchain_farm_state.last_update_time),
            amount_staked=onchain_farm_state.amount_staked,
        )[0]
        for i, reward_token in enumerate(onchain_farm_state_params.reward_tokens):
            db_farms.FarmRewardToken.get_or_create(
                farm_params=db_farm_state_params,
                token=add_token_token(reward_token),
                idx=i,
            )
        for i, emission_rate in enumerate(onchain_farm_state.emission_rates):
            db_farms.FarmEmissionRate.get_or_create(
                farm_params=db_farm_state_params,
                emission_rate=emission_rate,
                idx=i,
            )
        for i, cumulative_reward_per_token in enumerate(
            onchain_farm_state.cumulative_rewards_per_token
        ):
            db_farms.FarmCumulativeRewardPerToken.get_or_create(
                farm_params=db_farm_state_params,
                cumulative_reward_per_token_numerator=cumulative_reward_per_token.numerator,
                cumulative_reward_per_token_denominator=cumulative_reward_per_token.denominator,
                idx=i,
            )
        _db_farm_state = db_farms.FarmState.create(
            transaction_output=farm_output,
            farm_params=db_farm_state_params,
        )
