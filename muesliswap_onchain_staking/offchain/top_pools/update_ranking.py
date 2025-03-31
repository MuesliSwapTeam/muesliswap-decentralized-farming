import fire

from muesliswap_onchain_staking.onchain import top_pools
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
from muesliswap_onchain_staking.offchain.util import (
    with_min_lovelace,
    sorted_utxos,
    adjust_for_wrong_fee,
)


def main(
    wallet: str = "creator",
    old_rank: int = 0,
    new_rank: int = 1,
):
    top_pools_script, _, top_pools_address = get_contract(
        module_name(top_pools), compressed=True
    )

    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)

    top_pools_utxos = context.utxos(top_pools_address)
#    assert len(top_pools_utxos) == 1, "Expected one top pools UTxO."
    top_pools_input = top_pools_utxos[1]

    tx_inputs = sorted_utxos([top_pools_input] + payment_utxos)
    state_input_idx = tx_inputs.index(top_pools_input)
    prev_datum = top_pools.TopPoolState.from_cbor(top_pools_input.output.datum.cbor)

    # construct redeemer
    update_params_redeemer = Redeemer(
        top_pools.UpdateRanking(
            state_input_index=state_input_idx,
            state_output_index=0,
            old_rank=old_rank,
            new_rank=new_rank,
            new_token_name=prev_datum.pool_ranking[old_rank],
        )
    )

    # construct output datum
    pool_ranking = prev_datum.pool_ranking
    prev_old, prev_new = pool_ranking[old_rank], pool_ranking[new_rank]
    pool_ranking[old_rank] = prev_new
    pool_ranking[new_rank] = prev_old
    new_datum = top_pools.TopPoolState(
        params=top_pools.TopPoolParams(
            pool_rewards=prev_datum.params.pool_rewards,
        ),
        pool_ranking=pool_ranking,
    )

    # construct outputs
    top_pools_output = TransactionOutput(
        address=top_pools_address,
        amount=top_pools_input.output.amount,
        datum=new_datum,
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Update Top Pool Ranking"]}})
        )
    )
    # - add outputs
    builder.add_output(with_min_lovelace(top_pools_output, context))
    builder.validity_start = context.last_block_slot - 50
    builder.ttl = context.last_block_slot + 250
    # - add inputs
    for u in payment_utxos:
        builder.add_input(u)
    # - add script inputs
    builder.add_script_input(
        top_pools_input,
        top_pools_script,
        None,
        update_params_redeemer,
    )

    # sign the transaction
    signed_tx = builder.build_and_sign(
        signing_keys=[payment_skey],
        change_address=payment_address,
    )

    # submit the transaction
    context.submit_tx(
        adjust_for_wrong_fee(signed_tx, [payment_skey], fee_offset=100, output_offset=0)
    )

    show_tx(signed_tx)


if __name__ == "__main__":
    fire.Fire(main)
