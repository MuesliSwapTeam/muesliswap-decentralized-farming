import click
from pycardano import TransactionBuilder, TransactionOutput, Value

from muesliswap_onchain_staking.utils import get_signing_info, get_address
from muesliswap_onchain_staking.utils.network import context
from muesliswap_onchain_staking.offchain.util import token_from_string, asset_from_token, with_min_lovelace


@click.command()
@click.argument("name")
@click.argument("beneficiary")
@click.option(
    "--amount",
    type=int,
    default=10_000,
    help="Amount of lovelace to send to the beneficiary address.",
)
def main(name: str, beneficiary: str, amount: int):
    # Get payment address
    payment_address = get_address(name)

    # Get the beneficiary VerificationKeyHash (PubKeyHash)
    beneficiary_address = get_address(beneficiary)

    # Build the transaction
    builder = TransactionBuilder(context)
    builder.add_input_address(payment_address)
    builder.add_output(
        with_min_lovelace(
            TransactionOutput(
                address=beneficiary_address,
                amount=Value(
                    multi_asset=asset_from_token(
                        token_from_string(
                            "672ae1e79585ad1543ef6b4b6c8989a17adcea3040f77ede128d9217.6d7565736c69"
                        ),
                        amount,
                    )
                ),
            ),
            context,
        )
    )

    # Sign the transaction
    payment_vkey, payment_skey, payment_address = get_signing_info(name)
    signed_tx = builder.build_and_sign(
        signing_keys=[payment_skey],
        change_address=payment_address,
    )

    # Submit the transaction
    context.submit_tx(signed_tx.to_cbor())

    print(f"transaction id: {signed_tx.id}")
    print(f"Cardanoscan: https://preprod.cexplorer.io/tx/{signed_tx.id}")


if __name__ == "__main__":
    main()
