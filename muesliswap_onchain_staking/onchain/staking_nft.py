from opshin.prelude import *
from opshin.std.builtins import *
from muesliswap_onchain_staking.onchain.util import *
from muesliswap_onchain_staking.onchain.staking_types import *


# REDEEMERS ############################################################################################################
@dataclass
class MintApplyOrder(PlutusData):
    """
    Redeemer for applying order from batching contract to staking.
    """

    CONSTR_ID = 0
    farm_input_index: int
    staking_position_output_index: int


@dataclass
class BurnNFT(PlutusData):
    """
    Redeemer for unstaking.
    """

    CONSTR_ID = 1


StakingNFTRedeemer = Union[MintApplyOrder, BurnNFT]


def validator(
    staking_address: Address,
    redeemer: StakingNFTRedeemer,
    context: ScriptContext,
) -> None:
    purpose = get_minting_purpose(context)
    tx_info = context.tx_info

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
        assert farm_input.address == staking_address, "Invalid farm input."
        staking_position_output = tx_info.outputs[r.staking_position_output_index]
        assert (
            staking_position_output.address == staking_address
        ), "Stake not going to staking contract."
        staking_datum: StakingPosition = resolve_datum_unsafe(
            staking_position_output, tx_info
        )
        assert (
            staking_datum.batching_output_index == r.staking_position_output_index
        ), "Invalid batching output index provided."

        # TODO: check time etc. of initialization

    else:
        assert False, "Invalid redeemer type."
