from typing import List
import fire

from muesliswap_onchain_staking.onchain import batching, staking
from muesliswap_onchain_staking.utils.network import show_tx, context
from muesliswap_onchain_staking.utils import to_address
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
from muesliswap_onchain_staking.offchain.util import (
    asset_from_token,
    with_min_lovelace,
)
from pycardano import (
    Transaction,
    TransactionBuilder,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
    TransactionOutput,
    Value,
    Address,
    UTxO,
)
from opshin.prelude import Token, TokenName
from muesliswap_onchain_staking.api.tx_builder.util import select_utxos


async def place_stake_order(
    user_address: Address,
    stake_token: Token,
    stake_amount: int,
    pool_id: TokenName,
    utxos: List[UTxO] = None,
):
    _, _, stake_order_batching = get_contract(module_name(batching), compressed=True)
    _, _, staking_address = get_contract(module_name(staking), compressed=True)

    # construct the stake order datum
    stake_order_datum = batching.StakeOrder(
        owner=to_address(user_address),
        pool_id=pool_id,
    )

    # build the transaction
    builder = TransactionBuilder(context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Create Add Stake Order"]}})
        )
    )
    for u in select_utxos(
        address=user_address,
        ada_amount=2_000_000,
        policy_id=stake_token.policy_id,
        token_name=stake_token.token_name,
        token_amount=stake_amount,
        utxos=utxos,
    ):
        builder.add_input(u)

    # construct the output
    stake_order_output = TransactionOutput(
        address=stake_order_batching,
        amount=Value(
            multi_asset=asset_from_token(stake_token, stake_amount),
        ),
        datum=stake_order_datum,
    )

    builder.add_output(with_min_lovelace(stake_order_output, context))
    builder.ttl = context.last_block_slot + 100

    # sign the transaction
    tx_body = builder.build(
        change_address=user_address,
    )

    transaction = Transaction(
        transaction_body=tx_body,
        transaction_witness_set=builder.build_witness_set(),
        auxiliary_data=builder.auxiliary_data,
    )

    return transaction.to_cbor_hex()
