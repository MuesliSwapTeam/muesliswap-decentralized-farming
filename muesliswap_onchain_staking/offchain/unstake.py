import fire
from datetime import datetime

from muesliswap_onchain_staking.onchain import staking, stake_state_nft
from muesliswap_onchain_staking.onchain.util import floor_scale_fraction
from muesliswap_onchain_staking.utils.network import show_tx, context
from muesliswap_onchain_staking.utils import get_signing_info, network, from_address
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
from pycardano import (
    TransactionBuilder,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
    TransactionOutput,
    Redeemer,
    Value,
)
from opshin.std.fractions import sub_fraction
from util import (
    with_min_lovelace,
    sorted_utxos,
    amount_of_token_in_value,
    asset_from_token,
    adjust_for_wrong_fee,
)


def main(
    wallet: str = "staker",
):
    staking_script, _, staking_address = get_contract(
        module_name(staking), compressed=True
    )
    _, stake_state_nft_script_hash, _ = get_contract(
        module_name(stake_state_nft), compressed=True
    )

    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)

    staking_utxos = context.utxos(staking_address)
    for u in staking_utxos:
        if u.output.amount.multi_asset.get(stake_state_nft_script_hash):
            stake_state_input = u
            break
    assert stake_state_input, "No stake state found."

    staking_input = staking_utxos[0 if stake_state_input == staking_utxos[1] else 1]

    prev_stake_state_datum = staking.StakingState.from_cbor(
        stake_state_input.output.datum.cbor
    )
    staking_position_datum = staking.StakingPosition.from_cbor(
        staking_input.output.datum.cbor
    )

    tx_inputs = sorted_utxos([staking_input, stake_state_input] + payment_utxos)
    staking_position_input_index = tx_inputs.index(staking_input)
    stake_state_input_index = tx_inputs.index(stake_state_input)
    current_time = int(datetime.now().timestamp() * 1000)

    unlock_amount = amount_of_token_in_value(
        prev_stake_state_datum.params.stake_token, staking_input.output.amount
    )

    # construct redeemers
    stake_state_unstake_redeemer = Redeemer(
        staking.UnstakeState(
            state_input_index=stake_state_input_index,
            state_output_index=0,
            staking_position_input_index=staking_position_input_index,
            payment_output_index=1,
            current_time=current_time,
        )
    )
    staking_unstake_redeemer = Redeemer(
        staking.UnstakePosition(
            state_input_index=stake_state_input_index,
            staking_position_input_index=staking_position_input_index,
        )
    )

    # construct output datum
    new_cumulative_pool_rpts = staking.compute_updated_cumulative_rewards_per_token(
        prev_cum_rpts=prev_stake_state_datum.cumulative_rewards_per_token,
        emission_rates=prev_stake_state_datum.emission_rates,
        amount_staked=prev_stake_state_datum.amount_staked,
        last_update_time=prev_stake_state_datum.last_update_time,
        current_time=current_time,
    )
    stake_state_datum = staking.StakingState(
        params=prev_stake_state_datum.params,
        emission_rates=prev_stake_state_datum.emission_rates,
        last_update_time=current_time,
        amount_staked=prev_stake_state_datum.amount_staked - unlock_amount,
        cumulative_rewards_per_token=new_cumulative_pool_rpts,
    )

    # construct outputs
    stake_state_output = TransactionOutput(
        address=staking_address,
        amount=stake_state_input.output.amount,
        datum=stake_state_datum,
    )

    reward_amounts = [
        floor_scale_fraction(new_crpt, unlock_amount)
        - floor_scale_fraction(
            start_crpt,
            unlock_amount,
        )
        for new_crpt, start_crpt in zip(
            new_cumulative_pool_rpts,
            staking_position_datum.cumulative_pool_rpts_at_start,
        )
    ]
    reward_value = sum(
        [
            Value(multi_asset=asset_from_token(tk, am))
            for tk, am in zip(
                prev_stake_state_datum.params.reward_tokens, reward_amounts
            )
        ],
        Value(),
    )
    unlock_payment_output = TransactionOutput(
        address=from_address(staking_position_datum.owner),
        amount=staking_input.output.amount + reward_value,
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Unstaking and reward payout."]}})
        )
    )
    # - add outputs
    builder.add_output(stake_state_output)
    builder.add_output(unlock_payment_output)
    builder.add_output(
        with_min_lovelace(
            TransactionOutput(
                address=payment_address,
                amount=Value(
                    multi_asset=asset_from_token(
                        prev_stake_state_datum.params.reward_tokens[0],
                        998_673 - reward_amounts[0],
                    )
                ),
            ),
            context,
        )
    )
    builder.validity_start = context.last_block_slot - 50
    builder.ttl = context.last_block_slot + 100
    # - add inputs
    for u in payment_utxos:
        builder.add_input(u)
    # - add script inputs
    builder.add_script_input(
        stake_state_input,
        staking_script,
        None,
        stake_state_unstake_redeemer,
    )
    builder.add_script_input(
        staking_input,
        staking_script,
        None,
        staking_unstake_redeemer,
    )

    # sign the transaction
    signed_tx = builder.build_and_sign(
        signing_keys=[payment_skey],
        change_address=payment_address,
    )

    # submit the transaction
    context.submit_tx(
        adjust_for_wrong_fee(signed_tx, [payment_skey], fee_offset=0, output_offset=0)
    )

    show_tx(signed_tx)


if __name__ == "__main__":
    fire.Fire(main)
