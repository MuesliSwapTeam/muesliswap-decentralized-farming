import fire
from datetime import datetime

from muesliswap_onchain_staking.onchain import batching, stake_state, staking
from muesliswap_onchain_staking.utils.network import show_tx, context
from muesliswap_onchain_staking.utils import get_signing_info, network
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
from pycardano import (
    TransactionBuilder,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
    TransactionOutput,
    Redeemer,
)
from opshin.prelude import FinitePOSIXTime, POSIXTime
from util import (
    with_min_lovelace,
    sorted_utxos,
    amount_of_token_in_value,
    adjust_for_wrong_fee,
)


def main(
    wallet: str = "batcher",
):
    batching_script, _, batching_address = get_contract(
        module_name(batching), False
    )  # TODO: change to compressed
    stake_state_script, _, stake_state_address = get_contract(
        module_name(stake_state), False
    )  # TODO: change to compressed
    staking_script, _, staking_address = get_contract(
        module_name(staking), False
    )  # TODO: change to compressed

    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)

    batching_utxos = context.utxos(batching_address)
    stake_state_utxos = context.utxos(stake_state_address)

    print("Stake state UTxOs:", stake_state_utxos)
    print("Batching UTxOs:", batching_utxos)

    assert len(batching_utxos) == 1, "There should be exactly one batching UTxO."
    batching_input = batching_utxos[0]
    assert len(stake_state_utxos) == 1, "There should be exactly one stake state UTxO."
    stake_state_input = stake_state_utxos[0]

    add_stake_order_datum = batching.AddStakeOrder.from_cbor(
        batching_input.output.datum.cbor
    )
    prev_stake_state_datum = stake_state.StakingState.from_cbor(
        stake_state_input.output.datum.cbor
    )

    tx_inputs = sorted_utxos([batching_input, stake_state_input] + payment_utxos)
    order_input_index = tx_inputs.index(batching_input)
    stake_state_input_index = tx_inputs.index(stake_state_input)
    current_time = int(datetime.now().timestamp() * 1000)

    amount_to_stake = amount_of_token_in_value(
        prev_stake_state_datum.params.stake_token, batching_input.output.amount
    )

    # construct redeemers
    batching_apply_redeemer = Redeemer(
        batching.ApplyOrder(stake_state_input_index=stake_state_input_index)
    )
    stake_state_apply_redeemer = Redeemer(
        stake_state.ApplyOrders(
            state_input_index=stake_state_input_index,
            state_output_index=0,
            order_input_index=order_input_index,
            order_output_index=1,
            # license_input_index=0,
            current_time=current_time,
        )
    )

    # construct output datums
    new_cumulative_pool_rpt = stake_state.compute_updated_cumulative_rewards_per_token(
        prev_cum_rpt=prev_stake_state_datum.cumulative_rewards_per_token,
        emission_rate=prev_stake_state_datum.emission_rate,
        amount_staked=prev_stake_state_datum.amount_staked,
        last_update_time=prev_stake_state_datum.last_update_time,
        current_time=current_time,
    )
    stake_state_datum = stake_state.StakingState(
        params=prev_stake_state_datum.params,
        emission_rate=prev_stake_state_datum.emission_rate,
        last_update_time=current_time,
        amount_staked=prev_stake_state_datum.amount_staked + amount_to_stake,
        cumulative_rewards_per_token=new_cumulative_pool_rpt,
    )
    staking_position_datum = staking.StakingPosition(
        owner=add_stake_order_datum.owner,
        pool_id=add_stake_order_datum.pool_id,
        staked_since=current_time,
        cumulative_pool_rpt_at_start=new_cumulative_pool_rpt,
    )

    # construct outputs
    stake_state_output = TransactionOutput(
        address=stake_state_address,
        amount=stake_state_input.output.amount,
        datum=stake_state_datum,
    )
    staking_position_output = TransactionOutput(
        address=staking_address,
        amount=batching_input.output.amount,
        datum=staking_position_datum,
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Batch Add Stake Order"]}})
        )
    )
    # - add outputs
    builder.add_output(with_min_lovelace(stake_state_output, context))
    builder.add_output(with_min_lovelace(staking_position_output, context))
    builder.validity_start = context.last_block_slot - 50
    builder.ttl = context.last_block_slot + 100
    # - add inputs
    for u in payment_utxos:
        builder.add_input(u)
    # - add script inputs
    builder.add_script_input(
        stake_state_input,
        stake_state_script,
        None,
        stake_state_apply_redeemer,
    )
    builder.add_script_input(
        batching_input,
        batching_script,
        None,
        batching_apply_redeemer,
    )

    # sign the transaction
    signed_tx = builder.build_and_sign(
        signing_keys=[payment_skey],
        change_address=payment_address,
    )

    # submit the transaction
    context.submit_tx(
        adjust_for_wrong_fee(signed_tx, [payment_skey], fee_offset=77580)
    )

    show_tx(signed_tx)


if __name__ == "__main__":
    fire.Fire(main)
