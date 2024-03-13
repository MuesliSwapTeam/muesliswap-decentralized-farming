import fire

from muesliswap_onchain_staking.onchain import batching
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
from util import (
    token_from_string,
    asset_from_token,
    with_min_lovelace,
)


def main(
    wallet: str = "staker",
    stake_token: Token = token_from_string(
        "672ae1e79585ad1543ef6b4b6c8989a17adcea3040f77ede128d9217.6d7565736c69"
    ),
    stake_amount: int = 42,
    pool_id: Token = token_from_string("abcd.abcd"),
):
    _, _, stake_order_batching = get_contract(
        module_name(batching), False
    )  # TODO: change to compressed
    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)

    # construct the stake order datum
    stake_order_datum = batching.AddStakeOrder(
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
    stake_state_output = TransactionOutput(
        address=stake_order_batching,
        amount=Value(
            multi_asset=asset_from_token(stake_token, stake_amount),
        ),
        datum=stake_order_datum,
    )

    builder.add_output(with_min_lovelace(stake_state_output, context))
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
