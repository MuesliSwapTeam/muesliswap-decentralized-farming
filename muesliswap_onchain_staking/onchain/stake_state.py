from opshin.std.math import *
from muesliswap_onchain_staking.onchain.util import *
from muesliswap_onchain_staking.onchain.stake_state_types import *
from muesliswap_onchain_staking.onchain.staking_types import *
from muesliswap_onchain_staking.onchain.batching_types import *

MAX_VALIDITY_RANGE = 3 * 60 * 1000  # 3 minutes


# HELPER FUNCTIONS #####################################################################################################
def resolve_linear_output_state(
    next_state_output: TxOut, tx_info: TxInfo
) -> StakingState:
    """
    Resolve the continuing datum of the output that is referenced by the redeemer.
    """
    next_state: StakingState = resolve_datum_unsafe(next_state_output, tx_info)
    return next_state


def compute_updated_cumulative_rewards_per_token(
    prev_cum_rpts: List[int],
    emission_rates: List[int],
    amount_staked: int,
    last_update_time: POSIXTime,
    current_time: POSIXTime,
) -> List[int]:
    """
    Compute the updated cumulative reward per token.
    """
    return [
        prev_cum_rpts[i]
        + (
            0
            if amount_staked == 0
            else (
                (emission_rates[i] * (current_time - last_update_time)) // amount_staked
            )
        )
        for i in range(len(emission_rates))
    ]


# VALIDATOR ############################################################################################################
def validator(
    staking_address: Address,
    stake_state_nft_policy: PolicyId,
    previous_state: StakingState,
    redeemer: StakeStateRedeemer,
    context: ScriptContext,
) -> None:
    purpose = get_spending_purpose(context)
    tx_info = context.tx_info
    outputs = tx_info.outputs

    previous_state_input = resolve_linear_input(
        tx_info, redeemer.state_input_index, purpose
    )
    next_state_output = resolve_linear_output(
        previous_state_input, tx_info, redeemer.state_output_index
    )
    next_stake_state = resolve_linear_output_state(next_state_output, tx_info)
    check_preserves_value(previous_state_input, next_state_output)

    # Idea:
    #  - keep validity range short to enforce current_time to be approximately accurate (i.e. up to range)
    #  - last_update_time must be strictly increasing to prevent strange effects (e.g. negative rewards)
    assert range_is_short(
        tx_info.valid_range, MAX_VALIDITY_RANGE
    ), "Validity range longer than threshold."
    assert contained(
        tx_info.valid_range, redeemer.current_time
    ), "Current time outside of validity interval."
    assert (
        previous_state.last_update_time < redeemer.current_time
    ), "Update time must be strictly increasing."

    # Ensure authenticity of pool by checking that corret pool NFT is present
    assert (
        amount_of_token_in_output(
            Token(stake_state_nft_policy, previous_state.params.pool_id),
            previous_state_input,
        )
        == 1
    ), "Correct Pool NFT is not present."

    new_cumulative_pool_rpts = compute_updated_cumulative_rewards_per_token(
        previous_state.cumulative_rewards_per_token,
        previous_state.emission_rates,
        previous_state.amount_staked,
        previous_state.last_update_time,
        redeemer.current_time,
    )
    new_emission_rates = previous_state.emission_rates

    if isinstance(redeemer, ApplyOrders):
        r: ApplyOrders = redeemer

        # Idea: enforce strictly ascending in/out indices to ensure one-to-one mapping between inputs and outputs
        prev_order_input_index = -1
        prev_order_output_index = -1
        desired_amount_staked = previous_state.amount_staked

        for i in range(len(r.order_input_indices)):
            in_idx = r.order_input_indices[i]
            assert (
                in_idx > prev_order_input_index
            ), "Order inputs not in strictly ascending order."
            prev_order_input_index = in_idx
            out_idx = r.order_output_indices[i]
            assert (
                out_idx > prev_order_output_index
            ), "Order outputs not in strictly ascending order."
            prev_order_output_index = out_idx

            order_input = tx_info.inputs[in_idx].resolved
            order_datum: AddStakeOrder = resolve_datum_unsafe(order_input, tx_info)
            provided_amount = amount_of_token_in_output(
                previous_state.params.stake_token, order_input
            )
            desired_amount_staked += provided_amount

            stake_txout = outputs[out_idx]
            assert (
                stake_txout.address == staking_address
            ), "Order output doesn't send funds to staking address."
            stake_datum: StakingPosition = resolve_datum_unsafe(stake_txout, tx_info)
            assert (
                order_datum.pool_id == previous_state.params.pool_id
            ), "Invalid Pool ID."
            assert stake_datum.pool_id == order_datum.pool_id, "Pool ID mismatch."
            assert stake_datum.owner == order_datum.owner, "Owner mismatch."
            assert (
                stake_datum.staked_since == r.current_time
            ), "Invalid staked since time."
            assert lists_equal(
                stake_datum.cumulative_pool_rpts_at_start,
                next_stake_state.cumulative_rewards_per_token,
            ), "Cumulative reward per token set incorrectly in staking position datum."
            staked_amount = amount_of_token_in_output(
                previous_state.params.stake_token, stake_txout
            )
            assert staked_amount == provided_amount, "Staked amount < provided amount."

    elif isinstance(redeemer, UpdateParams):
        # for now, suppose the only thing we allow to update is the emission rates
        r: UpdateParams = redeemer
        for rt in r.new_emission_rates:
            assert rt >= 0, "Negative emission rate."
        new_emission_rates = r.new_emission_rates
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

        # check that owner receives the correct amount of reward tokens
        payment_output = tx_info.outputs[r.payment_output_index]
        expected_reward_amounts = [
            (
                (
                    new_cumulative_pool_rpts[i]
                    - staking_position_datum.cumulative_pool_rpts_at_start[i]
                )
                * staked_amount
            )
            // (24 * 60 * 60 * 1000)
            for i in range(len(previous_state.params.reward_tokens))
        ]
        expected_reward_value = sum_values(
            [
                value_from_token(
                    previous_state.params.reward_tokens[i], expected_reward_amounts[i]
                )
                for i in range(len(previous_state.params.reward_tokens))
            ]
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
        new_emission_rates,
        r.current_time,
        desired_amount_staked,
        new_cumulative_pool_rpts,
    )
    assert (
        desired_next_state == next_stake_state
    ), "Staking state not updated correctly."
