from onchain.util import *
from opshin.std.math import *


# DATUMS ##############################################################################################################
@dataclass
class StakingParams(PlutusData):
    """
    Non-updatable parameters of the staking contract
    """

    CONSTR_ID = 0
    pool_auth_nft: Token
    reward_token: Token  # TODO allow multiple reward tokens
    stake_token: Token


@dataclass
class StakingState(PlutusData):
    """
    Tracks emission and stakes.
    """

    CONSTR_ID = 0
    params: StakingParams
    emission_rate: int  # in reward tokens per day
    last_update_time: POSIXTime
    amount_staked: int
    cumulative_reward_per_token: int


# REDEEMERS ############################################################################################################
@dataclass
class ApplyOrders(PlutusData):
    """
    Redeemer for staking contract to apply batch of orders.
    """

    CONSTR_ID = 0
    state_input_index: int
    license_input_index: int
    order_input_index: int  # TODO allow multiple orders
    state_output_index: int
    current_time: POSIXTime


@dataclass
class Unstake(PlutusData):
    """
    Redeemer for unstaking.
    """

    CONSTR_ID = 1
    state_input_index: int
    order_input_index: int
    state_output_index: int
    current_time: POSIXTime


@dataclass
class UpdateParams(PlutusData):
    """
    Redeemer for updating staking reward parameters.
    """

    CONSTR_ID = 2
    state_input_index: int
    tally_input_index: int
    state_output_index: int
    current_time: POSIXTime


StakingRedeemer = Union[ApplyOrders, Unstake, UpdateParams]


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


def construct_desired_output_staking_state(
    previous_state: StakingState,
    redeemer: StakingRedeemer,
    tx_info: TxInfo,
    purpose: Spending,
) -> StakingState:
    if isinstance(redeemer, ApplyOrders):
        # update amount staked
        order_input = resolve_linear_input(tx_info, redeemer.order_input_index, purpose)
        provided_amount = amount_of_token_in_output(
            previous_state.params.stake_token, order_input
        )
        desired_amount_staked = previous_state.amount_staked + provided_amount

        # TODO check also that output is created with the correct amount of tokens and the correct datum

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
    return desired_next_state


# VALIDATOR ############################################################################################################
def validator(
    state: StakingState,
    redeemer: StakingRedeemer,
    context: ScriptContext,
) -> None:
    purpose = get_spending_purpose(context)
    tx_info = context.tx_info

    # get the previous state
    previous_state_input = resolve_linear_input(
        tx_info, redeemer.state_input_index, purpose
    )
    previous_state = resolve_linear_input_state(state)

    next_state_output = resolve_linear_output(
        previous_state_input, tx_info, redeemer.state_output_index
    )
    next_gov_state = resolve_linear_output_state(next_state_output, tx_info)
    desired_next_state = construct_desired_output_staking_state(
        previous_state, redeemer, tx_info, purpose
    )
    assert (
        desired_next_state == next_gov_state
    ), "Gov state must not change except for the last_proposal_id"
