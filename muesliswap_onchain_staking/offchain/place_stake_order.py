import fire

from muesliswap_onchain_staking.onchain import batching, staking
from muesliswap_onchain_staking.utils.network import show_tx, context
from muesliswap_onchain_staking.utils import get_signing_info, network, to_address
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
from muesliswap_onchain_staking.offchain.util import (
    token_from_string,
    asset_from_token,
    with_min_lovelace,
)
from pycardano import (
    TransactionBuilder,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
    TransactionOutput,
    Value,
)
from opshin.prelude import Token


def main(
    wallet: str = "staker",
    stake_token: Token = token_from_string(
        "672ae1e79585ad1543ef6b4b6c8989a17adcea3040f77ede128d9217.6d7565736c69"
    ),
    stake_amount: int = 100,
):
    _, _, stake_order_batching = get_contract(module_name(batching), compressed=True)
    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)

    # determine pool id from existing pool
    _, _, staking_address = get_contract(module_name(staking), compressed=True)
    staking_utxos = context.utxos(staking_address)
    assert len(staking_utxos) == 1, "There should be exactly one staking UTxO."
    farm_input = staking_utxos[0]
    farm_datum = staking.FarmState.from_cbor(
        farm_input.output.datum.cbor
    )
    pool_id = farm_datum.params.pool_id

    # construct the stake order datum
    stake_order_datum = batching.StakeOrder(
        owner=to_address(payment_address),
        pool_id=pool_id,
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Create Add Stake Order"]}})
        )
    )
    for u in payment_utxos:
        builder.add_input(u)

    # construct the output
    stake_order_output = TransactionOutput(
        address=stake_order_batching,
        amount=Value(
            multi_asset=asset_from_token(stake_token, stake_amount),
        ),
        datum=stake_order_datum,
    )

    builder.add_output(with_min_lovelace(stake_order_output, context))
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
