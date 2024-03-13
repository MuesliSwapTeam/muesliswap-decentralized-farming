from datetime import datetime
import fire

from muesliswap_onchain_staking.onchain import stake_state
from muesliswap_onchain_staking.utils.network import show_tx, context
from muesliswap_onchain_staking.utils import get_signing_info, network
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
from pycardano import (
    TransactionBuilder,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
    TransactionOutput,
)
from util import (
    token_from_string,
    with_min_lovelace,
)


def main(
    wallet: str = "creator",
    stake_amonut: int = 42_000_000,
):
    _, _, stake_state_address = get_contract(
        module_name(stake_state), False
    )  # TODO: change to compressed
    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)

    # construct the datum
    stake_state_datum = stake_state.StakingState(
        params=stake_state.StakingParams(
            pool_auth_nft=token_from_string("abcd.abcd"),
            reward_token=token_from_string("lovelace"),
            stake_token=token_from_string("lovelace"),
        ),
        emission_rate=10,
        last_update_time=int(datetime.now().timestamp() * 1000),
        amount_staked=stake_amonut,
        cumulative_reward_per_token=0,
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(metadata=Metadata({674: {"msg": ["Create Staking Pool"]}}))
    )
    for u in payment_utxos:
        builder.add_input(u)

    # construct the output
    stake_state_output = TransactionOutput(
        address=stake_state_address,
        amount=stake_amonut,
        datum=stake_state_datum,
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