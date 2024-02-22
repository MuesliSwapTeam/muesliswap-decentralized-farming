from opshin.prelude import *


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


@dataclass
class StakingPosition(PlutusData):
    """
    Datum for staking position UTxO's.
    """

    CONSTR_ID = 0
    owner: Address
    pool_id: TokenName
    staked_since: ExtendedPOSIXTime  # TODO don't use extended time
    cumulative_pool_rpt_at_start: int


@dataclass
class AddStakeOrder(PlutusData):
    """
    Datum for batching UTxOs: add new position to staking contract.
    """

    CONSTR_ID = 0
    owner: Address
    pool_id: TokenName


# REDEEMERS ############################################################################################################
@dataclass
class ApplyOrders(PlutusData):
    """
    Redeemer for staking contract to apply batch of orders.
    """

    CONSTR_ID = 0
    state_input_index: int
    state_output_index: int
    order_input_index: int  # TODO allow multiple orders
    order_output_index: int  # TODO allow multiple orders
    license_input_index: int
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
