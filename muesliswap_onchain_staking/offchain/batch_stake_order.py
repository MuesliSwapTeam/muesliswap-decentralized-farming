import fire

from muesliswap_onchain_staking.onchain import batching, stake_state, staking
from muesliswap_onchain_staking.utils.network import show_tx, context
from muesliswap_onchain_staking.utils import get_signing_info, network, to_address
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
from pycardano import (
    TransactionBuilder,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
    TransactionOutput,
    Value,
)
from opshin.prelude import Token
from util import with_min_lovelace, sorted_utxos


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

    batching_input = batching_utxos[0]
    assert len(stake_state_utxos) == 1, "There should be exactly one stake state UTxO."
    stake_state_input = stake_state_utxos[0]

    add_stake_order_datum = batching.AddStakeOrder.from_cbor(
        batching_input.output.datum.cbor
    )
    prev_stake_state_datum = stake_state.StakingState.from_cbor(
        stake_state_input.output.datum.cbor
    )

    important_inputs = sorted_utxos([batching_utxos[0], stake_state_utxos[0]])
    order_input_index = important_inputs.index(batching_utxos[0])
    stake_state_input_index = important_inputs.index(stake_state_utxos[0])
    current_slot = context.last_block_slot

    # construct redeemers
    batching_apply_redeemer = batching.ApplyOrder(
        stake_state_input_index=stake_state_input_index
    )
    stake_state_apply_redeemer = staking.ApplyOrders(
        state_input_index=stake_state_input_index,
        state_output_index=0,
        order_input_index=order_input_index,
        order_output_index=1,
        # license_input_index=0,
        current_time=current_slot,
    )

    # construct output datums
    stake_state_datum = stake_state.StakingState(
        params=prev_stake_state_datum.params,
        emission_rate=prev_stake_state_datum.emission_rate,
        last_update_time=current_slot,
        amount_staked=prev_stake_state_datum.amount_staked
        + add_stake_order_datum.stake_amount,
        cumulative_reward_per_token=prev_stake_state_datum.cumulative_reward_per_token,
    )
    staking_position_datum = staking.StakingPosition(
        owner=add_stake_order_datum.owner,
        pool_id=add_stake_order_datum.pool_id,
        staked_since=current_slot,
        cumulative_pool_rpt_at_start=prev_stake_state_datum.cumulative_reward_per_token,
    )

    # construct outputs
    stake_state_output = TransactionOutput(
        address=to_address(stake_state_address),
        amount=stake_state_input.amount,
        datum=stake_state_datum,
    )
    staking_position_output = TransactionOutput(
        address=to_address(add_stake_order_datum.pool_id),
        amount=batching_input.amount,
        datum=staking_position_datum,
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Batch Add Stake Order"]}})
        )
    )
    # - add inputs
    for u in important_inputs + payment_utxos:
        builder.add_input(u)
    # - add script inputs
    builder.add_script_input(
        stake_state_input, stake_state_script, None, stake_state_apply_redeemer
    )
    builder.add_script_input(
        batching_input, batching_script, None, batching_apply_redeemer
    )
    # - add outputs
    builder.add_output(with_min_lovelace(stake_state_output, context))
    builder.add_output(with_min_lovelace(staking_position_output, context))
    builder.ttl = context.last_block_slot + 100

    # sign the transaction
    signed_tx = builder.build_and_sign(
        signing_keys=[payment_skey],
        change_address=payment_address,
    )

    # submit the transaction
    context.submit_tx(signed_tx)

    show_tx(signed_tx)


if __name__ == "__main__":
    fire.Fire(main)
