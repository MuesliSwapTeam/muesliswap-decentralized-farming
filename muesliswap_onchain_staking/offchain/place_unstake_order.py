import fire

from muesliswap_onchain_staking.onchain import (
    batching,
    staking,
    stake_state_nft,
    unstake_permission_nft,
)
from muesliswap_onchain_staking.onchain.unstake_permission_nft import *
from muesliswap_onchain_staking.utils.network import show_tx, context
from muesliswap_onchain_staking.utils import (
    get_signing_info,
    network,
    to_address,
    to_tx_out_ref,
)
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
from pycardano import (
    TransactionBuilder,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
    TransactionOutput,
    Value,
    TransactionInput,
)
from opshin.prelude import Token, TokenName
from util import (
    asset_from_token,
    with_min_lovelace,
)


def main(
    wallet: str = "staker",
):
    _, _, stake_order_batching = get_contract(module_name(batching), compressed=True)
    _, _, staking_address = get_contract(module_name(staking), compressed=True)
    _, stake_state_nft_script_hash, _ = get_contract(
        module_name(stake_state_nft), compressed=True
    )
    unstake_permission_nft_script, unstake_permission_nft_pid, _ = get_contract(
        module_name(unstake_permission_nft), compressed=True
    )

    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    payment_utxos = context.utxos(payment_address)

    staking_utxos = context.utxos(staking_address)
    for u in staking_utxos:
        if not u.output.amount.multi_asset.get(stake_state_nft_script_hash):
            staking_position_input = u
            break
    assert staking_position_input, "No staking position found."

    unstake_order_datum = batching.UnstakeOrder(
        owner=to_address(payment_address),
        staking_position_input=to_tx_out_ref(
            TransactionInput(
                transaction_id=staking_position_input.input.transaction_id,
                index=staking_position_input.input.index,
            )
        ),
    )
    permission_nft_redeemer = UnstakePermissionNFTParams(
        owner=unstake_order_datum.owner,
        staking_position_input=unstake_order_datum.staking_position_input,
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(metadata=Metadata({674: {"msg": ["Place Unstake Order"]}}))
    )
    for u in payment_utxos:
        builder.add_input(u)

    # construct the output
    permission_nft_asset = asset_from_token(
        Token(
            policy_id=unstake_permission_nft_pid.payload,
            token_name=unstake_permission_nft_token_name(
                UnstakePermissionNFTParams(
                    owner=unstake_order_datum.owner,
                    staking_position_input=unstake_order_datum.staking_position_input,
                ),
            ),
        ),
        1,
    )
    stake_order_output = TransactionOutput(
        address=stake_order_batching,
        amount=Value(multi_asset=permission_nft_asset),
        datum=unstake_order_datum,
    )

    builder.add_output(with_min_lovelace(stake_order_output, context))
    builder.ttl = context.last_block_slot + 100
    builder.mint = permission_nft_asset
    builder.add_minting_script(unstake_permission_nft_script, permission_nft_redeemer)

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
