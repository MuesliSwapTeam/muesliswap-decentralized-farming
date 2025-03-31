import fire

from muesliswap_onchain_staking.onchain import batching
from muesliswap_onchain_staking.utils.network import show_tx, context
from muesliswap_onchain_staking.utils import get_signing_info, network
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
from pycardano import (
    TransactionBuilder,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
    Redeemer,
)


def main(
    wallet: str = "staker",
):
    batching_script, _, stake_order_batching = get_contract(
        module_name(batching), compressed=True
    )
    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)
    batching_utxos = context.utxos(stake_order_batching)
    utxo_to_cancel = batching_utxos[0]

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Cancel Add Stake Order"]}})
        )
    )
    for u in payment_utxos:
        builder.add_input(u)
    builder.add_script_input(
        utxo_to_cancel,
        batching_script,
        None,
        Redeemer(batching.CancelOrder()),
    )
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
