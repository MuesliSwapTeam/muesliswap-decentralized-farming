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
from util import (
    token_from_string,
    asset_from_token,
    with_min_lovelace,
)


def main(
    wallet: str = "batcher",
):
    _, _, batching_address = get_contract(
        module_name(batching), False
    )  # TODO: change to compressed
    _, _, stake_state_address = get_contract(
        module_name(stake_state), False
    )  # TODO: change to compressed
    _, _, staking_address = get_contract(
        module_name(staking), False
    )  # TODO: change to compressed

    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)

    batching_utxos = context.utxos(batching_address)
    stake_state_utxos = context.utxos(stake_state_address)

    add_stake_order = batching.AddStakeOrder.from_cbor(
        batching_utxos[0].output.datum.cbor
    )
    assert len(stake_state_utxos) == 1, "There should be exactly one stake state UTxO."
    prev_stake_state = stake_state.StakingState.from_cbor(
        stake_state_utxos[0].output.datum.cbor
    )

    # TODO construct ApplyOrder and ApplyOrders redeemer
    # TODO construct datums for new stake_state and staking_position

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
        address=stake_state_address,
        #        amount=Value(
        #            multi_asset=asset_from_token(stake_token, stake_amount),
        #        ),
        #        datum=stake_order_datum,
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
