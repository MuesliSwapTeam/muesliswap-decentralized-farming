import fire

from muesliswap_onchain_staking.onchain import batching, stake_state, staking
from muesliswap_onchain_staking.utils.network import show_tx, context
from muesliswap_onchain_staking.utils import get_signing_info, network, to_address
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
import pycardano
from pycardano import (
    TransactionBuilder,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
    TransactionOutput,
    Redeemer,
    Transaction,
    SigningKey,
    ExtendedSigningKey,
    VerificationKeyWitness,
)
from typing import List, Union
from opshin.prelude import FinitePOSIXTime, POSIXTime
from util import with_min_lovelace, sorted_utxos, amount_of_token_in_value


def adjust_for_wrong_fee(
    tx_signed: Transaction,
    signing_keys: List[Union[SigningKey, ExtendedSigningKey]],
    fee_offset: int = 0,
) -> Transaction:
    new_value = pycardano.transaction.Value(
        coin=tx_signed.transaction_body.outputs[-1].amount.coin - fee_offset
    )
    tx_signed.transaction_body.outputs[-1].amount = new_value

    witness_set = tx_signed.transaction_witness_set
    witness_set.vkey_witnesses = []
    for signing_key in set(signing_keys):
        signature = signing_key.sign(tx_signed.transaction_body.hash())
        witness_set.vkey_witnesses.append(
            VerificationKeyWitness(signing_key.to_verification_key(), signature)
        )
    return Transaction(tx_signed.transaction_body, witness_set, auxiliary_data=tx_signed.auxiliary_data)


def main(
    new_emission_rate: int = 42,
    wallet: str = "batcher",
):
    stake_state_script, _, stake_state_address = get_contract(
        module_name(stake_state), False
    )  # TODO: change to compressed

    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)
    stake_state_utxos = context.utxos(stake_state_address)
    assert len(stake_state_utxos) == 1, "There should be exactly one stake state UTxO."
    stake_state_input = stake_state_utxos[0]

    prev_stake_state_datum = stake_state.StakingState.from_cbor(
        stake_state_input.output.datum.cbor
    )

    tx_inputs = sorted_utxos([stake_state_input] + payment_utxos)
    stake_state_input_index = tx_inputs.index(stake_state_input)
    current_slot = context.last_block_slot

    # construct redeemers
    stake_state_apply_redeemer = Redeemer(
        stake_state.UpdateParams(
            state_input_index=stake_state_input_index,
            state_output_index=0,
            new_emission_rate=new_emission_rate,
            current_time=current_slot,
        )
    )

    # construct output datums
    new_cumulative_pool_rpt = stake_state.compute_updated_cumulative_reward_per_token(
        prev_cum_rpt=prev_stake_state_datum.cumulative_reward_per_token,
        emission_rate=prev_stake_state_datum.emission_rate,
        last_update_time=prev_stake_state_datum.last_update_time,
        current_time=current_slot,
    )
    stake_state_datum = stake_state.StakingState(
        params=prev_stake_state_datum.params,
        emission_rate=new_emission_rate,
        last_update_time=current_slot,
        amount_staked=prev_stake_state_datum.amount_staked,
        cumulative_reward_per_token=new_cumulative_pool_rpt,
    )

    # construct outputs
    stake_state_output = TransactionOutput(
        address=stake_state_address,
        amount=stake_state_input.output.amount,
        datum=stake_state_datum,
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Update Pool Emission Rate"]}})
        )
    )
    # - add outputs
    builder.add_output(with_min_lovelace(stake_state_output, context))
    builder.ttl = context.last_block_slot + 100
    # - add inputs
    for u in payment_utxos:
        builder.add_input(u)
    # - add script inputs
    builder.add_script_input(
        stake_state_input,
        stake_state_script,
        None,
        stake_state_apply_redeemer,
    )

    # sign the transaction
    signed_tx = builder.build_and_sign(
        signing_keys=[payment_skey],
        change_address=payment_address,
    )

    # submit the transaction
    context.submit_tx(adjust_for_wrong_fee(signed_tx, [payment_skey], fee_offset=12930))

    show_tx(signed_tx)


if __name__ == "__main__":
    fire.Fire(main)
