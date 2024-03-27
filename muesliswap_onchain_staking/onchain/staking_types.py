from opshin.prelude import *
from opshin.std.fractions import *


# DATUMS ##############################################################################################################
@dataclass
class StakingParams(PlutusData):
    """
    Non-updatable parameters of the staking contract
    """

    CONSTR_ID = 0
    pool_id: TokenName
    reward_tokens: List[Token]
    stake_token: Token


@dataclass
class StakingState(PlutusData):
    """
    Tracks emission and stakes.
    """

    CONSTR_ID = 0
    params: StakingParams
    emission_rates: List[int]  # in tokens per day
    last_update_time: POSIXTime
    amount_staked: int
    cumulative_rewards_per_token: List[Fraction]


@dataclass
class StakingPosition(PlutusData):
    """
    Datum for staking position UTxO's.
    """

    CONSTR_ID = 1
    owner: Address
    pool_id: TokenName
    staked_since: POSIXTime
    batching_output_index: int
    cumulative_pool_rpts_at_start: List[Fraction]


StakingDatum = Union[StakingState, StakingPosition]


# REDEEMERS ############################################################################################################
@dataclass
class ApplyOrders(PlutusData):
    """
    Redeemer for staking contract to apply batch of orders.
    """

    CONSTR_ID = 0
    state_input_index: int
    state_output_index: int
    order_input_indices: List[int]
    order_output_indices: List[int]
    # license_input_index: int  # TODO: support/require licenses
    current_time: POSIXTime


@dataclass
class UpdateParams(PlutusData):
    """
    Redeemer for updating staking reward parameters.
    """

    CONSTR_ID = 1
    state_input_index: int
    state_output_index: int
    new_emission_rates: List[int]
    current_time: POSIXTime


@dataclass
class UnstakeState(PlutusData):
    """
    Redeemer for unstaking.
    """

    CONSTR_ID = 2
    state_input_index: int
    state_output_index: int
    staking_position_input_index: int
    payment_output_index: int
    current_time: POSIXTime


@dataclass
class UnstakePosition(PlutusData):
    """
    Redeemer for unstaking.
    """

    CONSTR_ID = 3
    state_input_index: int
    staking_position_input_index: int


StakingRedeemer = Union[ApplyOrders, UpdateParams, UnstakePosition, UnstakeState]
StateRedeemer = Union[ApplyOrders, UpdateParams, UnstakeState]
