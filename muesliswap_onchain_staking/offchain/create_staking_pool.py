from datetime import datetime
import fire

from muesliswap_onchain_staking.onchain import stake_state, stake_state_nft
from muesliswap_onchain_staking.utils.network import show_tx, context
from muesliswap_onchain_staking.utils import get_signing_info, network
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
from muesliswap_onchain_staking.utils.to_script_context import to_tx_out_ref
from pycardano import (
    TransactionBuilder,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
    TransactionOutput,
    Redeemer,
    Value,
)
from opshin.prelude import Token
from util import (
    token_from_string,
    with_min_lovelace,
    asset_from_token
)


def main(
    wallet: str = "creator",
    stake_token: Token = token_from_string(
        "672ae1e79585ad1543ef6b4b6c8989a17adcea3040f77ede128d9217.6d7565736c69"
    ),
):
    _, _, stake_state_address = get_contract(
        module_name(stake_state), compressed=False
    )  # TODO: change to compressed
    stake_state_nft_script, stake_state_nft_policy_id, _ = get_contract(
        module_name(stake_state_nft), compressed=False
    )  # TODO: change to compressed
    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)

    # select UTxO to define the stake pool ID and generate expected stake_state_nft name
    unique_utxo = payment_utxos[0]
    stake_state_nft_name = stake_state_nft.stake_state_nft_name(to_tx_out_ref(unique_utxo.input))
    stake_state_nft_token = Token(
        policy_id=stake_state_nft_policy_id.payload,
        token_name=stake_state_nft_name,
    )

    # construct redeemer for the stake_state_nft
    stake_state_nft_redeemer = Redeemer(0)

    # construct the datum
    stake_state_datum = stake_state.StakingState(
        params=stake_state.StakingParams(
            pool_id=stake_state_nft_name,
            reward_token=stake_token,
            stake_token=stake_token,
        ),
        emission_rate=10,
        last_update_time=context.last_block_slot,
        amount_staked=0,
        cumulative_reward_per_token=0,
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(metadata=Metadata({674: {"msg": ["Create Staking Pool"]}}))
    )
    for u in payment_utxos:
        builder.add_input(u)
    builder.add_minting_script(stake_state_nft_script, stake_state_nft_redeemer)

    # construct the output
    stake_state_output = TransactionOutput(
        address=stake_state_address,
        amount=Value(coin=2000000, multi_asset=asset_from_token(stake_state_nft_token, 1)),
        datum=stake_state_datum,
    )

    builder.add_output(with_min_lovelace(stake_state_output, context))
    builder.mint = asset_from_token(stake_state_nft_token, 1)
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
