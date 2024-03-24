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
    staked_since: POSIXTime
    cumulative_pool_rpts_at_start: List[int]


# REDEEMERS ############################################################################################################
@dataclass
class UnstakingRedeemer(PlutusData):
    """
    Redeemer for unstaking.
    """

    CONSTR_ID = 1
    state_input_index: int
