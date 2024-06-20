import fire
from datetime import datetime

from muesliswap_onchain_staking.onchain import staking, farm_nft
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
from typing import List
from util import with_min_lovelace, sorted_utxos, adjust_for_wrong_fee


def main(
    new_emission_rates: List[int] = [43_000],
    wallet: str = "batcher",
):
    staking_script, _, staking_address = get_contract(
        module_name(staking), compressed=True
    )
    _, farm_nft_script_hash, _ = get_contract(
        module_name(farm_nft), compressed=True
    )

    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)
    staking_utxos = context.utxos(staking_address)

    for u in staking_utxos:
        if u.output.amount.multi_asset.get(farm_nft_script_hash):
            farm_input = u
            break
    assert farm_input, "No farm found."

    prev_farm_datum = staking.FarmState.from_cbor(
        farm_input.output.datum.cbor
    )

    tx_inputs = sorted_utxos([farm_input] + payment_utxos)
    farm_input_index = tx_inputs.index(farm_input)
    current_time = int(datetime.now().timestamp() * 1000)

    # construct redeemers
    farm_apply_redeemer = Redeemer(
        staking.UpdateParams(
            farm_input_index=farm_input_index,
            farm_output_index=0,
            new_emission_rates=new_emission_rates,
            current_time=current_time,
        )
    )

    # construct output datums
    new_cumulative_pool_rpts = staking.compute_updated_cumulative_rewards_per_token(
        prev_cum_rpts=prev_farm_datum.cumulative_rewards_per_token,
        emission_rates=prev_farm_datum.emission_rates,
        amount_staked=prev_farm_datum.amount_staked,
        last_update_time=prev_farm_datum.last_update_time,
        current_time=current_time,
    )
    farm_datum = staking.FarmState(
        params=prev_farm_datum.params,
        emission_rates=new_emission_rates,
        last_update_time=current_time,
        amount_staked=prev_farm_datum.amount_staked,
        cumulative_rewards_per_token=new_cumulative_pool_rpts,
    )

    # construct outputs
    farm_output = TransactionOutput(
        address=staking_address,
        amount=farm_input.output.amount,
        datum=farm_datum,
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Update Pool Emission Rate"]}})
        )
    )
    # - add outputs
    builder.add_output(with_min_lovelace(farm_output, context))
    builder.validity_start = context.last_block_slot - 50
    builder.ttl = context.last_block_slot + 100
    # - add inputs
    for u in payment_utxos:
        builder.add_input(u)
    # - add script inputs
    builder.add_script_input(
        farm_input,
        staking_script,
        None,
        farm_apply_redeemer,
    )

    # sign the transaction
    signed_tx = builder.build_and_sign(
        signing_keys=[payment_skey],
        change_address=payment_address,
    )

    # submit the transaction
    context.submit_tx(
        adjust_for_wrong_fee(
            signed_tx, [payment_skey], fee_offset=100, output_offset=64_650
        )
    )

    show_tx(signed_tx)


if __name__ == "__main__":
    fire.Fire(main)
