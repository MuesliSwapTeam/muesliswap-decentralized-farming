from onchain.util import *


# DATUMS ##############################################################################################################
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
class ApplyOrder(PlutusData):
    """
    Redeemer for applying order from batching contract to staking.
    """

    CONSTR_ID = 0
    staking_state_input_index: int


@dataclass
class CancelOrder(PlutusData):
    """
    Redeemer for unstaking.
    """

    CONSTR_ID = 1


BatchingRedeemer = Union[ApplyOrder, CancelOrder]


# VALIDATOR ############################################################################################################
def validator(
    staking_auth_nft_policy: PolicyId,
    datum: AddStakeOrder,
    redeemer: BatchingRedeemer,
    context: ScriptContext,
) -> None:
    purpose = get_spending_purpose(context)
    tx_info = context.tx_info

    if isinstance(redeemer, ApplyOrder):
        staking_input = resolve_linear_input(
            tx_info, redeemer.staking_state_input_index, purpose
        )
        staking_auth_nft = Token(staking_auth_nft_policy, datum.pool_id)
        assert token_present_in_output(
            staking_auth_nft, staking_input
        ), "Staking NFT not present in referenced input."

    elif isinstance(redeemer, CancelOrder):
        assert user_signed_tx(
            datum.owner, tx_info
        ), "Owner must sign cancel order transaction."
