from opshin.std.math import *
from muesliswap_onchain_staking.onchain.util import *
from muesliswap_onchain_staking.onchain.stake_state_types import *
from muesliswap_onchain_staking.onchain.staking_types import *
from muesliswap_onchain_staking.onchain.batching_types import *

MAX_VALIDITY_RANGE = 3 * 60 * 1000  # 3 minutes


# HELPER FUNCTIONS #####################################################################################################
def resolve_linear_input_state(datum: StakingState) -> StakingState:
    """
    Resolve the datum of the input that is referenced by the redeemer.
    """
    # TODO could compare datum with previous_state_input.datum, but maybe not necessary
    return datum


def resolve_linear_output_state(
    next_state_output: TxOut, tx_info: TxInfo
) -> StakingState:
    """
    Resolve the continuing datum of the output that is referenced by the redeemer.
    """
    next_state: StakingState = resolve_datum_unsafe(next_state_output, tx_info)
    return next_state


def compute_updated_cumulative_reward_per_token(
    prev_cum_rpt: int,
    emission_rate: int,
    last_update_time: POSIXTime,
    current_time: POSIXTime,
) -> int:
    """
    Compute the updated cumulative reward per token.
    """
    time_diff = current_time - last_update_time
    # TODO divide by 24*60*60*1000 and round to get the emission rate per day
    return prev_cum_rpt + (emission_rate * time_diff)


# VALIDATOR ############################################################################################################
def validator(
    staking_address: Address,
    stake_state_nft_policy: PolicyId,
    state: StakingState,
    redeemer: StakeStateRedeemer,
    context: ScriptContext,
) -> None:
    purpose = get_spending_purpose(context)
    tx_info = context.tx_info
    outputs = tx_info.outputs

    previous_state_input = resolve_linear_input(
        tx_info, redeemer.state_input_index, purpose
    )
    previous_state = resolve_linear_input_state(state)

    next_state_output = resolve_linear_output(
        previous_state_input, tx_info, redeemer.state_output_index
    )
    next_stake_state = resolve_linear_output_state(next_state_output, tx_info)
    check_preserves_value(previous_state_input, next_state_output)

    assert range_is_short(
        tx_info.valid_range, MAX_VALIDITY_RANGE
    ), "Validity range longer than threshold."

    new_cumulative_pool_rpt = compute_updated_cumulative_reward_per_token(
        previous_state.cumulative_reward_per_token,
        previous_state.emission_rate,
        previous_state.last_update_time,
        redeemer.current_time,
    )
    new_emission_rate = previous_state.emission_rate

    if isinstance(redeemer, ApplyOrders):
        r: ApplyOrders = redeemer

        order_input = tx_info.inputs[r.order_input_index].resolved
        order_datum: AddStakeOrder = resolve_datum_unsafe(order_input, tx_info)
        provided_amount = amount_of_token_in_output(
            previous_state.params.stake_token, order_input
        )
        desired_amount_staked = previous_state.amount_staked + provided_amount

        stake_txout = outputs[r.order_output_index]
        assert (
            stake_txout.address == staking_address
        ), "Order output doesn't send funds to staking address."
        stake_datum: StakingPosition = resolve_datum_unsafe(stake_txout, tx_info)
        assert isinstance(
            stake_datum, StakingPosition
        ), "Invalid staking position datum."
        assert (
            amount_of_token_in_output(
                Token(stake_state_nft_policy, stake_datum.pool_id),
                previous_state_input,
            )
            == 1
        ), "Correct Pool auth NFT is not present."
        assert stake_datum.pool_id == order_datum.pool_id, "Pool ID mismatch."
        assert stake_datum.owner == order_datum.owner, "Owner mismatch."
        assert (
            next_stake_state.cumulative_reward_per_token
            == stake_datum.cumulative_pool_rpt_at_start
        ), "Cumulative reward per token set incorrectly in staking position datum."
        assert contained(
            tx_info.valid_range, stake_datum.staked_since
        ), "Invalid staking time."
        staked_amount = amount_of_token_in_output(
            previous_state.params.stake_token, stake_txout
        )
        assert staked_amount == provided_amount, "Staked amount < provided amount."

    elif isinstance(redeemer, UpdateParams):
        r: UpdateParams = redeemer
        new_emission_rate = r.new_emission_rate
        desired_amount_staked = previous_state.amount_staked

    elif isinstance(redeemer, Unstake):
        r: Unstake = redeemer

        staking_position_input = tx_info.inputs[r.staking_position_input_index].resolved
        staking_position_datum: StakingPosition = resolve_datum_unsafe(
            staking_position_input, tx_info
        )
        staked_amount = amount_of_token_in_output(
            previous_state.params.stake_token, staking_position_input
        )
        desired_amount_staked = previous_state.amount_staked - staked_amount
        assert (
            desired_amount_staked >= 0
        ), "Unstake would result in negative amount staked."

        # check that owner receives the correct amount of reward tokens
        payment_output = tx_info.outputs[r.payment_output_index]
        expected_reward_amount = (
            new_cumulative_pool_rpt
            - staking_position_datum.cumulative_pool_rpt_at_start
        ) * staked_amount
        expected_reward_value = value_from_token(
            previous_state.params.reward_token, expected_reward_amount
        )
        check_greater_or_equal_value(
            add_value(staking_position_input.value, expected_reward_value),
            payment_output.value,
        )

    else:
        assert False, "Invalid redeemer."

    # in any case, check that cumulative reward per token is updated correctly
    desired_next_state = StakingState(
        previous_state.params,
        new_emission_rate,
        r.current_time,
        desired_amount_staked,
        new_cumulative_pool_rpt,
    )
    assert (
        desired_next_state == next_stake_state
    ), "Staking state not updated correctly."
    assert (
        previous_state.last_update_time < r.current_time
    ), "Invalid current time (w.r.t. last update time)."
    assert contained(
        tx_info.valid_range, r.current_time
    ), "Invalid current time in redeemer."
