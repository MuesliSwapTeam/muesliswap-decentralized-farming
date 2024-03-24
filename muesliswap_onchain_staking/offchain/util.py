from typing import List, Union

import pycardano

from opshin.prelude import Token
from pycardano import (
    MultiAsset,
    ScriptHash,
    Asset,
    AssetName,
    Value,
    Transaction,
    VerificationKeyWitness,
    SigningKey,
    ExtendedSigningKey,
)


def token_from_string(token: str) -> Token:
    if token == "lovelace":
        return Token(b"", b"")
    policy_id, token_name = token.split(".")
    return Token(
        policy_id=bytes.fromhex(policy_id),
        token_name=bytes.fromhex(token_name),
    )


def asset_from_token(token: Token, amount: int) -> MultiAsset:
    return MultiAsset(
        {ScriptHash(token.policy_id): Asset({AssetName(token.token_name): amount})}
    )


def with_min_lovelace(
    output: pycardano.TransactionOutput, context: pycardano.ChainContext
):
    min_lvl = pycardano.min_lovelace(context, output)
    output.amount.coin = max(output.amount.coin, min_lvl + 500000)
    return output


def sorted_utxos(txs: List[pycardano.UTxO]):
    return sorted(
        txs,
        key=lambda u: (u.input.transaction_id.payload, u.input.index),
    )


def amount_of_token_in_value(
    token: Token,
    value: Value,
) -> int:
    return value.multi_asset.get(ScriptHash(token.policy_id), {}).get(
        AssetName(token.token_name), 0
    )


def adjust_for_wrong_fee(
    tx_signed: Transaction,
    signing_keys: List[Union[SigningKey, ExtendedSigningKey]],
    output_offset: int = 0,
    fee_offset: int = 0,
) -> Transaction:
    new_value = pycardano.transaction.Value(
        coin=tx_signed.transaction_body.outputs[-1].amount.coin
        - output_offset
        - fee_offset
    )
    tx_signed.transaction_body.outputs[-1].amount = new_value
    tx_signed.transaction_body.fee += fee_offset

    witness_set = tx_signed.transaction_witness_set
    witness_set.vkey_witnesses = []
    for signing_key in set(signing_keys):
        signature = signing_key.sign(tx_signed.transaction_body.hash())
        witness_set.vkey_witnesses.append(
            VerificationKeyWitness(signing_key.to_verification_key(), signature)
        )
    return Transaction(
        tx_signed.transaction_body, witness_set, auxiliary_data=tx_signed.auxiliary_data
    )
