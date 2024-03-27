import fire
from datetime import datetime

from muesliswap_onchain_staking.onchain import batching, staking
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
        module_name(batching), compressed=True
    )
    staking_script, _, staking_address = get_contract(
        module_name(staking), compressed=True
    )
    _, _, staking_address = get_contract(module_name(staking), compressed=True)

    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)

    batching_utxos = context.utxos(batching_address)
    staking_utxos = context.utxos(staking_address)

    print("Stake state UTxOs:", staking_utxos)
    print("Batching UTxOs:", batching_utxos)

    assert len(staking_utxos) == 1, "There should be exactly one stake state UTxO."
    staking_input = staking_utxos[0]
    prev_stake_state_datum = staking.StakingState.from_cbor(
        staking_input.output.datum.cbor
    )

    tx_inputs = sorted_utxos(batching_utxos + [staking_input] + payment_utxos)
    order_inputs = sorted(
        [
            (
                tx_inputs.index(u),
                batching.AddStakeOrder.from_cbor(u.output.datum.cbor),
                u,
            )
            for u in batching_utxos
        ]
    )

    stake_state_input_index = tx_inputs.index(staking_input)
    current_time = int(datetime.now().timestamp() * 1000)
    total_amount_of_new_stake = sum(
        [
            amount_of_token_in_value(
                prev_stake_state_datum.params.stake_token, u.output.amount
            )
            for u in batching_utxos
        ]
    )

    # construct redeemers
    batching_apply_redeemers = [
        Redeemer(
            batching.ApplyOrder(
                stake_state_input_index=stake_state_input_index,
                staking_position_output_index=i + 1,
            )
        )
        for i in range(len(order_inputs))
    ]
    stake_state_apply_redeemer = Redeemer(
        staking.ApplyOrders(
            state_input_index=stake_state_input_index,
            state_output_index=0,
            order_input_indices=[o[0] for o in order_inputs],
            order_output_indices=[i + 1 for i in range(len(order_inputs))],
            current_time=current_time,
        )
    )

    # construct output datums
    new_cumulative_pool_rpts = staking.compute_updated_cumulative_rewards_per_token(
        prev_cum_rpts=prev_stake_state_datum.cumulative_rewards_per_token,
        emission_rates=prev_stake_state_datum.emission_rates,
        amount_staked=prev_stake_state_datum.amount_staked,
        last_update_time=prev_stake_state_datum.last_update_time,
        current_time=current_time,
    )
    stake_state_datum = staking.StakingState(
        params=prev_stake_state_datum.params,
        emission_rates=prev_stake_state_datum.emission_rates,
        last_update_time=current_time,
        amount_staked=prev_stake_state_datum.amount_staked + total_amount_of_new_stake,
        cumulative_rewards_per_token=new_cumulative_pool_rpts,
    )
    staking_position_datums = [
        staking.StakingPosition(
            owner=d.owner,
            pool_id=d.pool_id,
            staked_since=current_time,
            batching_output_index=i + 1,
            cumulative_pool_rpts_at_start=new_cumulative_pool_rpts,
        )
        for i, d in enumerate([o[1] for o in order_inputs])
    ]

    # construct outputs
    stake_state_output = TransactionOutput(
        address=staking_address,
        amount=staking_input.output.amount,
        datum=stake_state_datum,
    )
    staking_position_outputs = [
        TransactionOutput(
            address=staking_address,
            amount=order_inputs[i][2].output.amount,
            datum=d,
        )
        for i, d in enumerate(staking_position_datums)
    ]

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Batch Add Stake Order"]}})
        )
    )
    # - add outputs
    builder.add_output(with_min_lovelace(stake_state_output, context))
    for o in staking_position_outputs:
        builder.add_output(with_min_lovelace(o, context))
    builder.validity_start = context.last_block_slot - 50
    builder.ttl = context.last_block_slot + 100
    # - add inputs
    for u in payment_utxos:
        builder.add_input(u)
    # - add script inputs
    builder.add_script_input(
        staking_input,
        staking_script,
        None,
        stake_state_apply_redeemer,
    )
    for o, r in zip(order_inputs, batching_apply_redeemers):
        builder.add_script_input(
            o[2],
            batching_script,
            None,
            r,
        )

    # sign the transaction
    signed_tx = builder.build_and_sign(
        signing_keys=[payment_skey],
        change_address=payment_address,
    )

    # submit the transaction
    context.submit_tx(
        adjust_for_wrong_fee(
            signed_tx, [payment_skey], fee_offset=150, output_offset=155_160
        )
    )

    show_tx(signed_tx)


if __name__ == "__main__":
    fire.Fire(main)
