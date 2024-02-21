# create reference UTxOs
from time import sleep

from pycardano import TransactionBuilder, TransactionOutput, min_lovelace, Value

from .utils import network, get_signing_info
from .utils.contracts import get_contract, get_ref_utxo, module_name
from .utils.network import context, show_tx

from onchain import (
    staking,
    batching,
)


def main(compress: bool = True):
    owner = "scripts"
    _, payment_skey, payment_address = get_signing_info(
        owner, network=network
    )

    for contract in [
        staking,
        batching,
    ]:
        while True:
            try:
                contract_script, _, contract_address = get_contract(
                    module_name(contract), compressed=compress
                )
                ref_utxo = get_ref_utxo(contract_script, context)
                if ref_utxo:
                    print(
                        f"reference script UTXO for {module_name(contract)} already exists"
                    )
                    break
                txbuilder = TransactionBuilder(context)
                output = TransactionOutput(
                    contract_address, amount=1_000_000, script=contract_script
                )
                output.amount = Value(min_lovelace(context, output))
                txbuilder.add_output(output)
                txbuilder.add_input_address(payment_address)
                signed_tx = txbuilder.build_and_sign(
                    signing_keys=[payment_skey], change_address=payment_address
                )
                context.submit_tx(signed_tx)
                print(
                    f"creating {module_name(contract)} reference script UTXO; transaction id: {signed_tx.id}"
                )
                show_tx(signed_tx)
                break
            except KeyboardInterrupt:
                exit()
            except Exception as e:
                print(f"Error: {e}")
                sleep(30)


if __name__ == "__main__":
    main()
