from opshin.prelude import *


# DATUMS ##############################################################################################################
@dataclass
class AddStakeOrder(PlutusData):
    """
    Datum for batching UTxOs: add new position to staking contract.
    """

    CONSTR_ID = 0
    owner: Address
    pool_id: Token


# REDEEMERS ############################################################################################################
@dataclass
class ApplyOrder(PlutusData):
    """
    Redeemer for applying order from batching contract to staking.
    """

    CONSTR_ID = 0
    stake_state_input_index: int


@dataclass
class CancelOrder(PlutusData):
    """
    Redeemer for unstaking.
    """

    CONSTR_ID = 1


BatchingRedeemer = Union[ApplyOrder, CancelOrder]
