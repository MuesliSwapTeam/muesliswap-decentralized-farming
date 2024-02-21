from hashlib import sha256

from opshin.prelude import *
from onchain.utils.ext_interval import *
from opshin.std.builtins import *


def get_minting_purpose(context: ScriptContext) -> Minting:
    purpose = context.purpose
    assert isinstance(purpose, Minting)
    return purpose


def get_spending_purpose(context: ScriptContext) -> Spending:
    purpose = context.purpose
    assert isinstance(purpose, Spending)
    return purpose


def check_mint_exactly_n_with_name(
    mint: Value, n: int, policy_id: PolicyId, required_token_name: TokenName
) -> None:
    """
    Check that exactly n token with the given name is minted
    from the given policy
    """
    assert mint[policy_id][required_token_name] == n, "Exactly n token must be minted"
    assert len(mint[policy_id]) == 1, "No other token must be minted"


def check_mint_exactly_one_with_name(
    mint: Value, policy_id: PolicyId, required_token_name: TokenName
) -> None:
    """
    Check that exactly one token with the given name is minted
    from the given policy
    """
    check_mint_exactly_n_with_name(mint, 1, policy_id, required_token_name)


def token_present_in_output(token: Token, output: TxOut) -> bool:
    """
    Returns whether the given token is contained in the output
    """
    return output.value.get(token.policy_id, {b"": 0}).get(token.token_name, 0) > 0


def only_one_input_from_address(address: Address, inputs: List[TxInInfo]) -> bool:
    return sum([int(i.resolved.address == address) for i in inputs]) == 1


def only_one_output_to_address(address: Address, outputs: List[TxOut]) -> bool:
    return sum([int(i.address == address) for i in outputs]) == 1


def user_signed_tx(address: Address, tx_info: TxInfo) -> bool:
    return address.payment_credential.credential_hash in tx_info.signatories


def vote_has_ended(
    vote_deadline: ExtendedPOSIXTime, validity_range: POSIXTimeRange
) -> bool:
    return after_ext(validity_range, vote_deadline)


def amount_of_token_in_output(token: Token, output: TxOut) -> int:
    return output.value.get(token.policy_id, {b"": 0}).get(token.token_name, 0)


def resolve_linear_input(tx_info: TxInfo, input_index: int, purpose: Spending) -> TxOut:
    """
    Resolve the input that is referenced by the redeemer.
    Also checks that the input is referenced correctly and that there is only one.
    """
    previous_state_input_unresolved = tx_info.inputs[input_index]
    assert (
        previous_state_input_unresolved.out_ref == purpose.tx_out_ref
    ), f"Referenced wrong input"
    previous_state_input = previous_state_input_unresolved.resolved
    assert only_one_input_from_address(
        previous_state_input.address, tx_info.inputs
    ), "More than one input from the contract address"
    return previous_state_input


def resolve_linear_output(
    previous_state_input: TxOut, tx_info: TxInfo, output_index: int
) -> TxOut:
    """
    Resolve the continuing output that is referenced by the redeemer. Checks that the output does not move funds to a different address.
    """
    outputs = tx_info.outputs
    next_state_output = outputs[output_index]
    assert (
        next_state_output.address == previous_state_input.address
    ), "Moved funds to different address"
    assert only_one_output_to_address(
        next_state_output.address, outputs
    ), "More than one output to the contract address"
    return next_state_output


def check_mint_exactly_one_to_address(mint: Value, token: Token, staking_output: TxOut):
    """
    Check that exactly one token is minted and sent to address
    Also ensures that no other token of this policy is minted
    """
    check_mint_exactly_one_with_name(mint, token.policy_id, token.token_name)
    assert (
        amount_of_token_in_output(token, staking_output) == 1
    ), "Exactly one token must be sent to staking address"


def check_greater_or_equal_value(a: Value, b: Value) -> None:
    """
    Check that the value of a is greater or equal to the value of b, i.e. a >= b
    """
    for policy_id, tokens in b.items():
        for token_name, amount in tokens.items():
            assert (
                a.get(policy_id, {b"": 0}).get(token_name, 0) >= amount
            ), f"Value of {policy_id.hex()}.{token_name.hex()} is too low"


def check_preserves_value(
    previous_state_input: TxOut, next_state_output: TxOut
) -> None:
    """
    Check that the value of the previous state input is equal to the value of the next state output
    """
    previous_state_value = previous_state_input.value
    next_state_value = next_state_output.value
    check_greater_or_equal_value(next_state_value, previous_state_value)


def check_output_reasonably_sized(output: TxOut, attached_datum: Anything) -> None:
    """
    Check that the output is reasonably sized
    """
    assert len(output.to_cbor()) <= 1000, "Output value too large"
    assert len(serialise_data(attached_datum)) <= 1000, "Attached datum too large"


def list_index(listy: List[int], key: int) -> int:
    """
    Get the index of the first occurence of key in listy
    """
    index = 0
    for el in listy:
        if el == key:
            return index
        index += 1
    assert False, f"Key {key} not in list {listy}"
    return -1
