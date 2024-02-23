from opshin.std.math import *
from onchain.util import *
from onchain.staking_types import *
from onchain.stake_state_types import *


# VALIDATOR ############################################################################################################
def validator(
    datum: StakingPosition,
    redeemer: StakingRedeemer,
    context: ScriptContext,
) -> None:
    purpose = get_spending_purpose(context)
    tx_info = context.tx_info
    outputs = tx_info.outputs

    stake_state_input = resolve_linear_input(
        tx_info, redeemer.state_input_index, purpose
    )
    stake_state: StakingState = resolve_datum_unsafe(stake_state_input, tx_info)
    assert token_present_in_output(
        stake_state.params.pool_auth_nft, stake_state_input
    ), "Pool auth NFT not present in stake_state_input."
    assert (
        datum.pool_id == stake_state.params.pool_auth_nft.token_name
    ), "Referenced wrong pool in stake_state_input."

    staking_position_input = resolve_linear_input(
        tx_info, redeemer.order_input_index, purpose
    )

    if isinstance(redeemer, Unstake):
        assert user_signed_tx(datum.owner, tx_info), "Owner did not sign transaction."

        amount_of_token_in_output(stake_state.params.stake_token, stake_state_input)
        total_rewards = 0
        for o in outputs:
            total_rewards += amount_of_token_in_output(
                stake_state.params.reward_token, o
            )
        expected_rewards = (
            stake_state.cumulative_reward_per_token - datum.cumulative_pool_rpt_at_start
        ) * amount_of_token_in_output(
            stake_state.params.stake_token, staking_position_input
        )  # TODO change cum_rpt to value from stake_state output
        assert (
            total_rewards <= expected_rewards
        ), "Paid out amount is more than expected."

    else:
        assert False, "Invalid redeemer."
