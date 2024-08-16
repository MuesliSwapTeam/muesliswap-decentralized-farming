from datetime import datetime
import fire

from muesliswap_onchain_staking.onchain import staking, farm_nft
from muesliswap_onchain_staking.utils.network import show_tx, context
from muesliswap_onchain_staking.utils import get_signing_info, network
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
from muesliswap_onchain_staking.utils.to_script_context import to_tx_out_ref
from muesliswap_onchain_staking.offchain.util import (
    token_from_string,
    with_min_lovelace,
    asset_from_token,
    adjust_for_wrong_fee,
)
from pycardano import (
    TransactionBuilder,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
    TransactionOutput,
    Redeemer,
    Value,
)
from typing import List
from opshin.prelude import Token
from opshin.std.fractions import Fraction


def main(
    wallet: str = "creator",
    stake_token: Token = token_from_string(
        "672ae1e79585ad1543ef6b4b6c8989a17adcea3040f77ede128d9217.6d7565736c69"
    ),
    reward_tokens: List[Token] = [
        token_from_string(
            "672ae1e79585ad1543ef6b4b6c8989a17adcea3040f77ede128d9217.6d7565736c69"
        )
    ],
    emission_rates: List[int] = [42_000],
):
    _, _, staking_address = get_contract(module_name(staking), compressed=True)
    farm_nft_script, farm_nft_policy_id, _ = get_contract(
        module_name(farm_nft), compressed=True
    )
    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)

    # select UTxO to define the stake pool ID and generate expected farm_nft name
    unique_utxo = payment_utxos[0]
    farm_nft_name = farm_nft.farm_nft_name(to_tx_out_ref(unique_utxo.input))
    farm_nft_token = Token(
        policy_id=farm_nft_policy_id.payload,
        token_name=farm_nft_name,
    )

    # construct redeemer for the farm_nft
    farm_nft_redeemer = Redeemer(0)

    # construct the datum
    staking_farm_datum = staking.FarmState(
        params=staking.FarmParams(
            pool_id=farm_nft_name,
            reward_tokens=reward_tokens,
            stake_token=stake_token,
        ),
        farm_type=staking.DefaultFarmType(),
        emission_rates=emission_rates,
        last_update_time=int(datetime.now().timestamp() * 1000),
        amount_staked=0,
        cumulative_rewards_per_token=[Fraction(0, 1)] * len(reward_tokens),
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(metadata=Metadata({674: {"msg": ["Create Staking Pool"]}}))
    )
    for u in payment_utxos:
        builder.add_input(u)
    builder.add_minting_script(farm_nft_script, farm_nft_redeemer)

    # construct the output
    farm_output = TransactionOutput(
        address=staking_address,
        amount=Value(coin=2000000, multi_asset=asset_from_token(farm_nft_token, 1)),
        datum=staking_farm_datum,
    )

    builder.add_output(with_min_lovelace(farm_output, context))
    builder.mint = asset_from_token(farm_nft_token, 1)
    builder.ttl = context.last_block_slot + 100

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
