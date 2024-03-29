from opshin.prelude import *


# DATUMS ##############################################################################################################
@dataclass
class AddStakeOrder(PlutusData):
    """
    Datum for batching UTxOs: add new position to staking contract.
    """

    CONSTR_ID = 0
    owner: Address
    pool_id: TokenName


@dataclass
class UnstakeOrder(PlutusData):
    """
    Datum for batching UTxOs: remove position from staking contract.
    """

    CONSTR_ID = 1
    owner: Address
    staking_position: TxOutRef

#StakeOrderDatum = Union[AddStakeOrder, UnstakeOrder]


# REDEEMERS ############################################################################################################
@dataclass
class ApplyOrder(PlutusData):
    """
    Redeemer for applying order from batching contract to staking.
    """

    CONSTR_ID = 1
    stake_state_input_index: int
    staking_position_output_index: int


@dataclass
class CancelOrder(PlutusData):
    """
    Redeemer for unstaking.
    """

    CONSTR_ID = 2


BatchingRedeemer = Union[ApplyOrder, CancelOrder]
