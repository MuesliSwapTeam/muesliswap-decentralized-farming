import fire

from muesliswap_onchain_staking.onchain import top_pools
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
from muesliswap_onchain_staking.offchain.util import (
    with_min_lovelace,
)


def main(
    wallet: str = "creator",
):
    _, payment_skey, payment_address = get_signing_info(wallet, network=network)
    _, _, top_pools_address = get_contract(module_name(top_pools), compressed=True)

    top_pool_params_datum = top_pools.TopPoolParams(
        pool_rewards=[1, 2, 3, 4, 5]
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Init Top Pool Rewards"]}})
        )
    )
    builder.add_input_address(payment_address)
    builder.add_output(with_min_lovelace(TransactionOutput(
        address=top_pools_address,
        amount=0,
        datum=top_pool_params_datum,
    ), context))

    signed_tx = builder.build_and_sign(
        signing_keys=[payment_skey],
        change_address=payment_address,
    )
    context.submit_tx(signed_tx)
    show_tx(signed_tx)


if __name__ == "__main__":
    fire.Fire(main)
