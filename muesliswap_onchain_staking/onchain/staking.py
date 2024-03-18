from opshin.std.math import *
from muesliswap_onchain_staking.onchain.util import *
from muesliswap_onchain_staking.onchain.staking_types import *
from muesliswap_onchain_staking.onchain.stake_state_types import *


# VALIDATOR ############################################################################################################
def validator(
    stake_state_nft_policy: PolicyId,
    datum: StakingPosition,
    redeemer: UnstakingRedeemer,
    context: ScriptContext,
) -> None:
    purpose = get_spending_purpose(context)
    tx_info = context.tx_info
    outputs = tx_info.outputs

    assert isinstance(redeemer, UnstakingRedeemer), "Invalid redeemer."
    r: UnstakingRedeemer = redeemer

    stake_state_input = tx_info.inputs[r.state_input_index].resolved
    stake_state: StakingState = resolve_datum_unsafe(stake_state_input, tx_info)
    assert token_present_in_output(
        Token(stake_state_nft_policy, datum.pool_id), stake_state_input
    ), "Pool auth NFT not present in stake_state_input."
    # TODO check that pool auth NFT is also in output
    
    assert (
        datum.pool_id == stake_state.params.pool_id
    ), "Referenced wrong pool in stake_state_input."
    
    assert user_signed_tx(datum.owner, tx_info), "Owner did not sign transaction."