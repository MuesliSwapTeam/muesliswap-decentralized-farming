from opshin.prelude import *


# DATUMS ##############################################################################################################
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


# REDEEMERS ############################################################################################################
@dataclass
class Unstake(PlutusData):
    """
    Redeemer for unstaking.
    """

    CONSTR_ID = 0
    state_input_index: int
    order_input_index: int
    state_output_index: int
    current_time: POSIXTime


StakingRedeemer = Union[Unstake]
