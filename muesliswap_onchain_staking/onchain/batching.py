from muesliswap_onchain_staking.onchain.util import *
from muesliswap_onchain_staking.onchain.batching_types import *


# VALIDATOR ############################################################################################################
def validator(
    stake_state_nft_policy: PolicyId,
    datum: AddStakeOrder,
    redeemer: BatchingRedeemer,
    context: ScriptContext,
) -> None:
    tx_info = context.tx_info

    if isinstance(redeemer, ApplyOrder):
        stake_state_input = tx_info.inputs[redeemer.stake_state_input_index].resolved
        assert token_present_in_output(
            Token(stake_state_nft_policy, datum.pool_id), stake_state_input
        ), "Stake State NFT not present in referenced input."

    elif isinstance(redeemer, CancelOrder):
        assert user_signed_tx(
            datum.owner, tx_info
        ), "Owner must sign cancel order transaction."

    else:
        assert False, "Invalid redeemer type."
