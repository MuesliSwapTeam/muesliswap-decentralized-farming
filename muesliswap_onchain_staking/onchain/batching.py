from muesliswap_onchain_staking.onchain.util import *
from muesliswap_onchain_staking.onchain.batching_types import *
from muesliswap_onchain_staking.onchain.staking_types import *


# VALIDATOR ############################################################################################################
def validator(
    staking_address: Address,
    datum: AddStakeOrder,
    redeemer: BatchingRedeemer,
    context: ScriptContext,
) -> None:
    tx_info = context.tx_info

    if isinstance(redeemer, ApplyOrder):
        stake_state_input = tx_info.inputs[redeemer.stake_state_input_index].resolved
        assert (
            stake_state_input.address == staking_address
        ), "Invalid stake state input."
        staking_position_output = tx_info.outputs[
            redeemer.staking_position_output_index
        ]
        assert (
            staking_position_output.address == staking_address
        ), "Stake not going to staking contract."
        staking_datum: StakingPosition = resolve_datum_unsafe(staking_position_output, tx_info)
        assert (
            staking_datum.batching_output_index
            == redeemer.staking_position_output_index
        ), "Invalid batching output index provided."

    elif isinstance(redeemer, CancelOrder):
        assert user_signed_tx(
            datum.owner, tx_info
        ), "Owner must sign cancel order transaction."

    else:
        assert False, "Invalid redeemer type."
