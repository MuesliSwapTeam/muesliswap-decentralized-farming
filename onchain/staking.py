from opshin.std.math import *
from onchain.util import *
#from onchain.utils.ext_interval import *
from onchain.staking_types import *
from onchain.batching_types import *


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
    state: StakingState,
    redeemer: StakingRedeemer,
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
    )  # TODO need to allow multiple outputs to staking contract here (at least for ApplyOrders)
    next_stake_state = resolve_linear_output_state(next_state_output, tx_info)

    if isinstance(redeemer, ApplyOrders):
        order_input = resolve_linear_input(tx_info, redeemer.order_input_index, purpose)
        order_datum: AddStakeOrder = resolve_datum_unsafe(order_input, tx_info)
        provided_amount = amount_of_token_in_output(
            previous_state.params.stake_token, order_input
        )
        desired_amount_staked = previous_state.amount_staked + provided_amount

        stake_txout = outputs[redeemer.order_output_index]
        assert (
            stake_txout.address == previous_state_input.address
        ), "Referenced order output index does not send funds to staking address."
        stake_datum: StakingPosition = resolve_datum_unsafe(stake_txout, tx_info)
        assert isinstance(
            stake_datum, StakingPosition
        ), "Invalid staking position datum."
        assert stake_datum.pool_id == order_datum.pool_id, "Pool ID mismatch."
        assert (
            next_stake_state.cumulative_reward_per_token
            == stake_datum.cumulative_pool_rpt_at_start
        ), "Cumulative reward per token set incorrectly in staking position datum."
        assert contained_ext(
            tx_info.valid_range, stake_datum.staked_since
        ), "Invalid staking time."
        assert range_is_short(
            tx_info.valid_range, 5 * 60 * 1000
        ), "Validity range longer than threshold."

        staked_amount = amount_of_token_in_output(
            previous_state.params.stake_token, stake_txout
        )
        assert staked_amount == provided_amount, "Staked amount < provided amount."

    elif isinstance(redeemer, Unstake):
        # TODO make sure owner (written in staking position's datum (TODO define this)) has signed tx
        # TODO check that paid out amount is no more than rewards earned since start of staking (TODO compute from cum_rpt at staking time stored in staking position's datum)
        desired_amount_staked = (
            previous_state.amount_staked
        )  # TODO subtract amount unstaked
        pass

    elif isinstance(redeemer, UpdateParams):
        desired_amount_staked = previous_state.amount_staked
        # TODO check that propor vote outcome is provided?
        pass

    else:
        assert False, "Invalid redeemer."

    desired_next_state = StakingState(
        previous_state.params,
        previous_state.emission_rate,
        redeemer.current_time,
        desired_amount_staked,
        compute_updated_cumulative_reward_per_token(
            previous_state.cumulative_reward_per_token,
            previous_state.emission_rate,
            previous_state.last_update_time,
            redeemer.current_time,
        ),
    )
    assert (
        desired_next_state == next_stake_state
    ), "Staking state not updated correctly."
