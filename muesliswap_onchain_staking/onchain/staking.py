from opshin.prelude import *
from opshin.std.math import *
from muesliswap_onchain_staking.onchain.util import *
from muesliswap_onchain_staking.onchain.staking_types import *
from muesliswap_onchain_staking.onchain.batching_types import *

MAX_VALIDITY_RANGE = 3 * 60 * 1000  # 3 minutes
MILLIS_IN_DAY = 24 * 60 * 60 * 1000


# HELPER FUNCTIONS #####################################################################################################
def resolve_linear_output_state(next_farm_output: TxOut, tx_info: TxInfo) -> FarmState:
    """
    Resolve the continuing datum of the output that is referenced by the redeemer.
    """
    next_state: FarmState = resolve_datum_unsafe(next_farm_output, tx_info)
    return next_state


def check_valid_current_time(
    current_time: POSIXTime, last_update_time: POSIXTime, tx_info: TxInfo
) -> None:
    # Idea:
    #  - keep validity range short to enforce current_time to be approximately accurate (i.e. up to range)
    #  - last_update_time must be strictly increasing to prevent strange effects (e.g. negative rewards)
    assert range_is_short(
        tx_info.valid_range, MAX_VALIDITY_RANGE
    ), "Validity range longer than threshold."
    assert contained(
        tx_info.valid_range, current_time
    ), "Current time outside of validity interval."
    assert last_update_time < current_time, "Update time must be strictly increasing."


def compute_updated_cumulative_rewards_per_token(
    prev_cum_rpts: List[Fraction],
    emission_rates: List[int],
    amount_staked: int,
    last_update_time: POSIXTime,
    current_time: POSIXTime,
) -> List[Fraction]:
    """
    Compute the updated cumulative reward per token.
    """
    # TODO: fraction computations can probably be optimized
    return [
        (
            prev_cum_rpts[i]
            if amount_staked == 0
            else add_fraction(
                prev_cum_rpts[i],
                Fraction(
                    emission_rates[i] * (current_time - last_update_time),
                    amount_staked * MILLIS_IN_DAY,
                ),
            )
        )
        for i in range(len(emission_rates))
    ]


# VALIDATOR ############################################################################################################
# compile with --force-three-params
def validator(
    farm_nft_policy: PolicyId,
    unstake_permission_nft_policy: PolicyId,
    datum: StakingDatum,
    redeemer: StakingRedeemer,
    context: ScriptContext,
) -> None:
    purpose = context.purpose
    tx_info = context.tx_info
    if isinstance(purpose, Minting):
        policy_id = purpose.policy_id
        address = own_address(policy_id)
    elif isinstance(purpose, Spending):
        own_utxo_input = own_spent_utxo(tx_info.inputs, purpose)
        policy_id = own_policy_id(own_utxo_input)
        address = own_utxo_input.address
    else:
        assert False, "Wrong purpose"

    if isinstance(purpose, Minting):
        if isinstance(redeemer, BurnNFT):
            # Burning NFTs is always allowed
            # but we need to make sure that all mints with this policy are burning
            own_mint = tx_info.mint[purpose.policy_id]
            assert all(
                [amount < 0 for amount in own_mint.values()]
            ), "NFTs can only be burned with the burn redeemer"
        elif isinstance(redeemer, MintApplyOrder):
            r: MintApplyOrder = redeemer
            farm_input = tx_info.inputs[r.farm_input_index].resolved
            assert farm_input.address == address, "Invalid farm input."
            staking_position_output = tx_info.outputs[r.staking_position_output_index]
            assert (
                staking_position_output.address == address
            ), "Stake not going to staking contract."
            farm_datum: FarmState = resolve_datum_unsafe(
                farm_input, tx_info
            )  # TODO: check if this is safe
            assert isinstance(farm_datum, FarmState), "Invalid farm datum."
            staking_datum: StakingPosition = resolve_datum_unsafe(
                staking_position_output, tx_info
            )
            assert (
                staking_datum.batching_output_index == r.staking_position_output_index
            ), "Invalid batching output index provided."
            check_mint_exactly_one_with_name(
                tx_info.mint, purpose.policy_id, STAKE_NFT_NAME
            )

            # TODO: check time etc. of initialization -> not necessary since already checked in farm/staking contract (which we ensure above is spent)
        else:
            assert False, "Invalid redeemer type."

    elif isinstance(purpose, Spending):
        if isinstance(redeemer, UnstakePosition):
            r: UnstakePosition = redeemer
            assert isinstance(datum, StakingPosition), "Invalid datum type."
            d: StakingPosition = datum

            own_input_info = context.tx_info.inputs[r.staking_position_input_index]
            assert (
                own_input_info.out_ref == purpose.tx_out_ref
            ), "Index of own input does not match purpose"

            farm_input = tx_info.inputs[r.farm_input_index].resolved
            assert farm_input.address == address, "Invalid farm input."

            assert token_present_in_output(
                Token(farm_nft_policy, d.pool_id), farm_input
            ), "Pool NFT is not present in farm input."

            # check existence of respective order with matching unstake permission NFT
            unstake_order = tx_info.inputs[r.unstaking_order_input_index].resolved
            order_datum: UnstakeOrder = resolve_datum_unsafe(unstake_order, tx_info)
            assert order_datum.owner == d.owner, "Owner mismatch."
            assert (
                order_datum.staking_position == own_input_info.out_ref
            ), "Invalid unstake order."
            check_correct_stake_factory_nft(
                own_input_info.resolved,
                policy_id,
            )
            check_correct_unstake_permission_nft(
                unstake_order,
                unstake_permission_nft_policy,
                order_datum,
            )

        else:  # meaning we're spending the farm UTxO
            assert isinstance(datum, FarmState), "Invalid datum type."
            outputs = tx_info.outputs

            sr: FarmRedeemer = redeemer
            previous_farm_input = resolve_linear_input_unsafe(
                tx_info, sr.farm_input_index, purpose
            )
            previous_state: FarmState = datum
            next_farm_output = resolve_linear_output_unsafe(
                previous_farm_input, tx_info, sr.farm_output_index
            )
            next_farm = resolve_linear_output_state(next_farm_output, tx_info)
            check_preserves_value(previous_farm_input, next_farm_output)

            own_input_info = tx_info.inputs[sr.farm_input_index]
            assert (
                own_input_info.out_ref == purpose.tx_out_ref
            ), "Index of own (state) input does not match purpose"

            check_valid_current_time(
                sr.current_time, previous_state.last_update_time, tx_info
            )

            # Ensure authenticity of pool by checking that corret pool NFT is present
            assert (
                amount_of_token_in_output(
                    Token(farm_nft_policy, previous_state.params.pool_id),
                    previous_farm_input,
                )
                == 1
            ), "Correct Pool NFT is not present."

            new_cumulative_pool_rpts = compute_updated_cumulative_rewards_per_token(
                previous_state.cumulative_rewards_per_token,
                previous_state.emission_rates,
                previous_state.amount_staked,
                previous_state.last_update_time,
                sr.current_time,
            )
            new_emission_rates = previous_state.emission_rates

            if isinstance(redeemer, ApplyOrders):
                r: ApplyOrders = redeemer

                # Idea: enforce strictly ascending in/out indices to ensure one-to-one mapping between inputs and outputs
                prev_order_input_index = -1
                prev_order_output_index = -1
                desired_amount_staked = previous_state.amount_staked
                no_new_stakes, no_unstakes = 0, 0

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
                    order_datum = resolve_datum_unsafe(order_input, tx_info)

                    if isinstance(order_datum, StakeOrder):
                        od: StakeOrder = order_datum
                        provided_amount = amount_of_token_in_output(
                            previous_state.params.stake_token, order_input
                        )
                        desired_amount_staked += provided_amount
                        no_new_stakes += 1

                        stake_txout = outputs[out_idx]
                        out_datum = resolve_datum_unsafe(stake_txout, tx_info)
                        assert isinstance(
                            out_datum, StakingPosition
                        ), "Invalid output datum type."
                        stake_datum: StakingPosition = out_datum

                        assert (
                            od.pool_id == previous_state.params.pool_id
                        ), "Invalid Pool ID."
                        assert stake_datum.pool_id == od.pool_id, "Pool ID mismatch."
                        assert stake_datum.owner == od.owner, "Owner mismatch."
                        assert (
                            stake_datum.staked_since == r.current_time
                        ), "Invalid staked since time."
                        assert fract_lists_equal(
                            stake_datum.cumulative_pool_rpts_at_start,
                            next_farm.cumulative_rewards_per_token,
                        ), "Cumulative reward per token set incorrectly in staking position datum."
                        staked_amount = amount_of_token_in_output(
                            previous_state.params.stake_token, stake_txout
                        )
                        assert (
                            staked_amount == provided_amount
                        ), "Staked amount < provided amount."
                        assert (
                            out_idx == stake_datum.batching_output_index
                        ), "Batching output index mismatch."

                    elif isinstance(order_datum, UnstakeOrder):
                        od: UnstakeOrder = order_datum
                        staking_position_input = tx_info.inputs[
                            r.staking_position_input_indices[i]
                        ].resolved
                        staking_position_datum: StakingPosition = resolve_datum_unsafe(
                            staking_position_input, tx_info
                        )
                        no_unstakes += 1

                        assert (
                            od.staking_position == tx_info.inputs[in_idx].out_ref
                        ), "Invalid reference to staking position."
                        assert (
                            staking_position_input.address == address
                        ), "Invalid staking position."
                        unstaked_amount = amount_of_token_in_output(
                            previous_state.params.stake_token, staking_position_input
                        )
                        desired_amount_staked -= unstaked_amount

                        # check that owner cannot claim more than expected reward
                        payment_output = tx_info.outputs[out_idx]
                        expected_reward_amounts = [
                            floor_scale_fraction(
                                new_cumulative_pool_rpts[i], unstaked_amount
                            )
                            - floor_scale_fraction(
                                staking_position_datum.cumulative_pool_rpts_at_start[i],
                                unstaked_amount,
                            )
                            for i in range(len(previous_state.params.reward_tokens))
                        ]
                        expected_reward_value = sum_values(
                            [
                                value_from_token(
                                    previous_state.params.reward_tokens[i],
                                    expected_reward_amounts[i],
                                )
                                for i in range(len(previous_state.params.reward_tokens))
                            ]
                        )
                        check_greater_or_equal_value(
                            add_value(
                                staking_position_input.value, expected_reward_value
                            ),
                            payment_output.value,
                        )

                    else:
                        assert False, "Invalid order datum."

                assert exactly_n_outputs_to_address(
                    address, tx_info.outputs, no_new_stakes + 1
                ), "Creating too many new staking positions."
                assert exactly_n_inputs_from_address(
                    address, tx_info.inputs, no_unstakes + 1
                ), "Spending too many staking positions."

            elif isinstance(redeemer, UpdateParams):
                # for now, suppose the only thing we allow to update is the emission rates
                r: UpdateParams = redeemer
                for rt in r.new_emission_rates:
                    assert rt >= 0, "Negative emission rate."
                new_emission_rates = r.new_emission_rates
                desired_amount_staked = previous_state.amount_staked

                # ensure that no staking positions can be spent
                only_one_input_from_address(address, tx_info.inputs)

            else:
                assert False, "Invalid redeemer provided."

            # in any case, check that cumulative reward per token is updated correctly
            desired_next_state = FarmState(
                previous_state.params,
                previous_state.farm_type,
                new_emission_rates,
                r.current_time,
                desired_amount_staked,
                new_cumulative_pool_rpts,
            )
            assert (
                desired_next_state == next_farm
            ), "Staking state not updated correctly."

    else:
        assert False, "Invalid purpose."
