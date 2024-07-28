from opshin.prelude import *
from muesliswap_onchain_staking.onchain.util import *


# DATUMS ##############################################################################################################
@dataclass
class TopPoolParams(PlutusData):
    CONSTR_ID = 0
    pool_rewards: List[int]


# REDEEMERS ############################################################################################################
@dataclass
class UpdateParams(PlutusData):
    CONSTR_ID = 0
    updated_reward_index: int
    updated_amount: int
    state_input_index: int
    state_output_index: int


def resolve_linear_output_state(
    next_state_output: TxOut, tx_info: TxInfo
) -> TopPoolParams:
    """
    Resolve the continuing datum of the output that is referenced by the redeemer.
    """
    next_state: TopPoolParams = resolve_datum_unsafe(next_state_output, tx_info)
    return next_state


def check_list_updated_correctly(
    pool_rewards_before: List[int],
    pool_rewards_after: List[int],
    updated_reward_index: int,
    updated_amount: int,
) -> None:
    len_before = len(pool_rewards_before)
    len_after = len(pool_rewards_after)
    if updated_reward_index > len_before or updated_reward_index < 0:
        assert False, "Invalid reward index."
    elif updated_reward_index == len_before:
        assert len_after == len_before + 1, "Invalid list output length."
        for i in range(len_before):
            assert (
                pool_rewards_after[i] == pool_rewards_before[i]
            ), "Updated at invalid index."
        assert pool_rewards_after[-1] == updated_amount, "Invalid updated amount."
    else:
        assert len_after == len_before, "Invalid list output length."
        for i in range(len_before):
            if i != updated_reward_index:
                assert (
                    pool_rewards_after[i] == pool_rewards_before[i]
                ), "Updated at invalid index."
            else:
                assert (
                    pool_rewards_after[i] == updated_amount
                ), "Invalid updated amount."


def validator(
    datum: TopPoolParams,
    redeemer: UpdateParams,
    context: ScriptContext,
) -> None:
    tx_info = context.tx_info
    purpose = get_spending_purpose(context)
    input_state: TxOut = resolve_linear_input(
        tx_info, redeemer.state_input_index, purpose
    )
    next_state_output = resolve_linear_output(
        input_state, tx_info, redeemer.state_output_index
    )
    next_state = resolve_linear_output_state(next_state_output, tx_info)
    # TODO: require winning gov proposal to update
    check_list_updated_correctly(
        datum.pool_rewards,
        next_state.pool_rewards,
        redeemer.updated_reward_index,
        redeemer.updated_amount,
    )
