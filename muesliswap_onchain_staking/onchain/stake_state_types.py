from opshin.prelude import *


# DATUMS ##############################################################################################################
@dataclass
class StakingParams(PlutusData):
    """
    Non-updatable parameters of the staking contract
    """

    CONSTR_ID = 0
    pool_id: TokenName
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

    CONSTR_ID = 1
    state_input_index: int
    state_output_index: int
    order_input_index: int  # TODO allow multiple orders
    order_output_index: int  # TODO allow multiple orders
    # license_input_index: int
    current_time: POSIXTime


@dataclass
class UpdateParams(PlutusData):
    """
    Redeemer for updating staking reward parameters.
    """

    CONSTR_ID = 2
    state_input_index: int
    state_output_index: int
    new_emission_rate: int
    current_time: POSIXTime


@dataclass
class Unstake(PlutusData):
    """
    Redeemer for unstaking.
    """

    CONSTR_ID = 3
    state_input_index: int
    state_output_index: int
    staking_position_input_index: int
    payment_output_index: int
    current_time: POSIXTime


StakeStateRedeemer = Union[ApplyOrders, UpdateParams, Unstake]
