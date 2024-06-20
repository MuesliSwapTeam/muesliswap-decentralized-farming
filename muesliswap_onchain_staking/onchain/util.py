from hashlib import sha256

from opshin.prelude import *
from opshin.std.builtins import *
from opshin.std.fractions import *
from muesliswap_onchain_staking.onchain.utils.ext_interval import *
from muesliswap_onchain_staking.onchain.batching_types import *

EMTPY_TOKENNAME_DICT: Dict[bytes, int] = {}
EMPTY_VALUE_DICT: Value = {}


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


def exactly_n_inputs_from_address(address: Address, inputs: List[TxInInfo], n: int) -> bool:
    return sum([int(i.resolved.address == address) for i in inputs]) == n


def only_one_output_to_address(address: Address, outputs: List[TxOut]) -> bool:
    return sum([int(i.address == address) for i in outputs]) == 1


def exactly_n_outputs_to_address(address: Address, outputs: List[TxOut], n: int) -> bool:
    return sum([int(i.address == address) for i in outputs]) == n


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


def resolve_linear_input_unsafe(
    tx_info: TxInfo, input_index: int, purpose: Spending
) -> TxOut:
    """
    Resolve the input that is referenced by the redeemer.
    Also checks that the input is referenced correctly.
    *Does not* enforce having only one input from the contract address.
    """
    previous_state_input_unresolved = tx_info.inputs[input_index]
    assert (
        previous_state_input_unresolved.out_ref == purpose.tx_out_ref
    ), f"Referenced wrong input"
    previous_state_input = previous_state_input_unresolved.resolved
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


def resolve_linear_output_unsafe(
    previous_state_input: TxOut, tx_info: TxInfo, output_index: int
) -> TxOut:
    """
    Resolve the continuing output that is referenced by the redeemer. *Does not* enforce having only one output to the contract address.
    """
    outputs = tx_info.outputs
    next_state_output = outputs[output_index]
    assert (
        next_state_output.address == previous_state_input.address
    ), "Moved funds to different address"
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


def unstake_permission_nft_token_name(params: UnstakeOrder) -> TokenName:
    return blake2b_256(params.to_cbor())


def check_correct_unstake_permission_nft(
    order_input: TxOut,
    unstake_permission_nft_policy: PolicyId,
    unstake_permission_nft_params: UnstakeOrder,
) -> None:
    desired_nft_name = unstake_permission_nft_token_name(unstake_permission_nft_params)
    assert (
        amount_of_token_in_output(
            Token(unstake_permission_nft_policy, desired_nft_name), order_input
        )
        == 1
    ), "Not exactly one unstake permission NFT in order input"


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


def fract_lists_equal(a: List[Fraction], b: List[Fraction]) -> bool:
    """
    Check if two lists are equal
    """
    return len(a) == len(b) and all([a[i] == b[i] for i in range(len(a))])


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


def merge_without_duplicates(a: List[bytes], b: List[bytes]) -> List[bytes]:
    """
    Merge two lists without duplicates
    Note: The cost of this is O(n^2), can we assume that the lists are small?
    Rough estimate allows 1000 bytes / 32 bytes per policy id ~ 31 policy ids
    However for token names no lower bound on the length is given, so we assume 1000 bytes / 1 byte per token name ~ 1000 token names
    """
    return [x for x in a if not x in b] + b


def _subtract_token_names(
    a: Dict[TokenName, int], b: Dict[TokenName, int]
) -> Dict[TokenName, int]:
    """
    Subtract b from a, return a - b
    """
    if not b:
        return a
    elif not a:
        return {tn_amount[0]: -tn_amount[1] for tn_amount in b.items()}
    return {
        tn: a.get(tn, 0) - b.get(tn, 0)
        for tn in merge_without_duplicates(a.keys(), b.keys())
    }


def subtract_value(a: Value, b: Value) -> Value:
    """
    Subtract b from a, return a - b
    """
    if not b:
        return a
    elif not a:
        return {
            pid_tokens[0]: {
                tn_amount[0]: -tn_amount[1] for tn_amount in pid_tokens[1].items()
            }
            for pid_tokens in b.items()
        }
    return {
        pid: _subtract_token_names(
            a.get(pid, EMTPY_TOKENNAME_DICT), b.get(pid, EMTPY_TOKENNAME_DICT)
        )
        for pid in merge_without_duplicates(a.keys(), b.keys())
    }


def _add_token_names(
    a: Dict[TokenName, int], b: Dict[TokenName, int]
) -> Dict[TokenName, int]:
    """
    Add b to a, return a + b
    """
    if not a:
        return b
    if not b:
        return a
    return {
        tn: a.get(tn, 0) + b.get(tn, 0)
        for tn in merge_without_duplicates(a.keys(), b.keys())
    }


def add_value(a: Value, b: Value) -> Value:
    """
    Add b to a, return a + b
    """
    if not a:
        return b
    if not b:
        return a
    return {
        pid: _add_token_names(
            a.get(pid, EMTPY_TOKENNAME_DICT), b.get(pid, EMTPY_TOKENNAME_DICT)
        )
        for pid in merge_without_duplicates(a.keys(), b.keys())
    }


def sum_values(values: List[Value]) -> Value:
    """
    Sum up all values in the list
    """
    total_value = EMPTY_VALUE_DICT
    for v in values:
        total_value = add_value(total_value, v)
    return total_value


def total_value(value_store_inputs: List[TxOut]) -> Value:
    """
    Calculate the total value of all inputs
    """
    total_value = EMPTY_VALUE_DICT
    for txo in value_store_inputs:
        total_value = add_value(total_value, txo.value)
    return total_value


def amount_of_token_in_value(
    token: Token,
    value: Value,
) -> int:
    return value.get(token.policy_id, {b"": 0}).get(token.token_name, 0)


def value_from_token(token: Token, amount: int) -> Value:
    return {token.policy_id: {token.token_name: amount}}


def floor_scale_fraction(f: Fraction, s: int) -> int:
    """
    Returns floor(f * s)
    """
    return (f.numerator * s) // f.denominator
