from opshin.prelude import *
from muesliswap_onchain_staking.onchain.util import *


# DATUMS ##############################################################################################################
@dataclass
class TopPoolParams(PlutusData):
    CONSTR_ID = 0
    pool_rewards: List[int]


class TopPoolState(PlutusData):
    CONSTR_ID = 0
    top_pool_params: TopPoolParams
    pool_ranking: List[TokenName]


# REDEEMERS ############################################################################################################
@dataclass
class UpdateParams(PlutusData):
    CONSTR_ID = 0
    state_input_index: int
    state_output_index: int
    updated_reward_index: int
    updated_amount: int


@dataclass
class UpdateRanking(PlutusData):
    CONSTR_ID = 0
    state_input_index: int
    state_output_index: int
    old_rank: int
    new_rank: int


TopPoolRedeemer = Union[UpdateParams, UpdateRanking]


def resolve_linear_output_state(
    next_state_output: TxOut, tx_info: TxInfo
) -> TopPoolState:
    """
    Resolve the continuing datum of the output that is referenced by the redeemer.
    """
    next_state: TopPoolState = resolve_datum_unsafe(next_state_output, tx_info)
    return next_state


def check_ranking_updated_correctly(
    ranking_before: List[TokenName],
    ranking_after: List[TokenName],
    old_rank: int,
    new_rank: int,
    new_pool_id: Union[None, TokenName],
) -> None:
    len = len(ranking_after)
    assert 0 <= new_rank < len and 0 <= old_rank
    assert old_rank < len or new_pool_id is not None
    for i in range(len):
        if i < old_rank and i < new_rank:
            assert ranking_after[i] == ranking_before[i]
        elif old_rank <= i <= new_rank:
            if i == new_rank:
                assert ranking_after[i] == (
                    ranking_before[old_rank] if old_rank < len else new_pool_id
                )
            else:
                if i + 1 < len:
                    assert ranking_after[i + 1] == ranking_before[i]
        elif old_rank >= i >= new_rank:
            if i == new_rank:
                assert ranking_after[i] == ranking_before[old_rank]
            else:
                assert ranking_after[i - 1] == ranking_before[i]
        elif i > ranking_before and i > ranking_after:
            assert ranking_after[i] == ranking_before[i]


def check_rewards_updated_correctly(
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
    datum: TopPoolState,
    redeemer: TopPoolRedeemer,
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

    if isinstance(redeemer, UpdateParams):
        r: UpdateParams = redeemer
        # TODO: require winning gov proposal to update
        check_rewards_updated_correctly(
            datum.pool_rewards,
            next_state.pool_rewards,
            r.updated_reward_index,
            r.updated_amount,
        )

    elif isinstance(redeemer, UpdateRanking):
        r: UpdateRanking = redeemer
        check_ranking_updated_correctly(
            datum.pool_ranking, next_state.pool_ranking, r.old_rank, r.new_rank
        )

    else:
        assert False, "Redeemer type unknown"