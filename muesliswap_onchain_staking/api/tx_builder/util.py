from typing import List
from pycardano import (
    Address,
    TransactionOutput,
    LargestFirstSelector,
    MultiAsset,
    Asset,
    Value,
    ScriptHash,
    AssetName,
    UTxO,
    Transaction,
)
from blockfrost.utils import list_request_wrapper
from pycardano.exception import InsufficientUTxOBalanceException
import os
import requests
from muesliswap_onchain_staking.utils.network import context
from opshin.prelude import Token

ADA = Token(policy_id=b"", token_name=b"")


def select_utxos(
    address: Address,
    ada_amount: int,
    policy_id: str = None,
    token_name: str = None,
    token_amount: int = None,
    multi_address: bool = False,
    utxos: List[UTxO] = None,
) -> List[UTxO]:
    """
    Selects UTxOs for ADA and given token (if provided)

    If utxos are provided, they are used instead of fetching from eg. Blockfrost
    If no utxos are provided, the function will fetch based on the address
    (if multi_address is False) or the account (if multi_address is True)
    """
    print(policy_id, token_name)
    print(type(policy_id), type(token_name))
    encoded_address = address.encode()
    if not utxos:
        utxos = context.utxos(address)
    if policy_id and token_name:
        request = [
            TransactionOutput.from_primitive(
                [
                    encoded_address,
                    [
                        ada_amount,
                        {
                            bytes.fromhex(f"{policy_id}"): {
                                bytes.fromhex(token_name): token_amount
                            }
                        },
                    ],
                ]
            )
        ]
    else:
        request = [TransactionOutput.from_primitive([encoded_address, ada_amount])]

    selector = LargestFirstSelector()
    try:
        selected, _ = selector.select(utxos, request, context)
    except InsufficientUTxOBalanceException as e:
        # Create dict showing what was requested
        requested = {"": ada_amount}
        if policy_id and token_name:
            requested.update({f"{policy_id}.{token_name}": token_amount})
        raise InsufficientUTxOBalanceException(f"Tried to request: {requested}")
    return selected


def assets_to_value(assets):
    """
    Converts a list of assets to a value
    """
    coin = 0

    multi_asset = MultiAsset()

    for asset in assets:
        token = Token.from_hex(asset["token"])
        if token == ADA:
            # Should only occur once
            coin += int(asset["amount"])
        else:
            temp = Asset({AssetName(bytes.fromhex(token.name)): int(asset["amount"])})
            policy_id = ScriptHash(bytes.fromhex(token.policy_id))
            if policy_id in multi_asset:
                multi_asset[policy_id].update(temp)
            else:
                multi_asset[policy_id] = temp

    value = Value(coin, multi_asset)
    return value


def value_from_utxos(utxos: List[UTxO]) -> Value:
    total_value = Value(0)
    for utxo in utxos:
        total_value += utxo.output.amount
    return total_value


def tokens_to_value(tokens: List[Token]):
    pass


def sign_and_submit(transaction_unsigned: Transaction, is_sundae=False):
    from pycardano import (
        PaymentSigningKey,
        PaymentVerificationKey,
        VerificationKeyWitness,
    )

    DISABLE_SUBMIT = False
    if not is_sundae:
        signing_key = PaymentSigningKey.load(os.getenv("test_user_key_path"))
        verification_key = PaymentVerificationKey.from_signing_key(signing_key)
    else:
        signing_key = PaymentSigningKey.load(os.getenv("test_user_with_stake_key_path"))
        verification_key = PaymentVerificationKey.from_signing_key(signing_key)

    signature = signing_key.sign(transaction_unsigned.transaction_body.hash())
    vk_witnesses = [VerificationKeyWitness(verification_key, signature)]

    transaction_witness_set = transaction_unsigned.transaction_witness_set

    if transaction_witness_set.vkey_witnesses is None:
        transaction_witness_set.vkey_witnesses = vk_witnesses
    else:
        transaction_witness_set.vkey_witnesses += vk_witnesses

    signed_tx = Transaction(
        transaction_unsigned.transaction_body,
        transaction_witness_set,
        transaction_unsigned.valid,
        transaction_unsigned.auxiliary_data,
    )
    print(signed_tx.to_cbor_hex())
    if DISABLE_SUBMIT:
        return None
    else:
        tx_hash = context.submit_tx(signed_tx)
        print(tx_hash)
        return tx_hash


@list_request_wrapper
def fetch_account_utxos(stake_address: Address, **kwargs):
    return requests.get(
        url=f"{context.api.url}/accounts/{stake_address}/utxos",
        params=context.api.query_parameters(kwargs),
        headers=context.api.default_headers,
    )
