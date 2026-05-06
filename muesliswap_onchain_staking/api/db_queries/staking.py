from datetime import datetime
from fractions import Fraction

from ..db_models import sqlite_db


MILLIS_IN_DAY = 24 * 60 * 60 * 1000


def _datetime_to_posix_ms(value) -> int:
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def _floor_scale_fraction(value: Fraction, scale: int) -> int:
    return value.numerator * scale // value.denominator


def _project_cumulative_rewards_per_token(
    numerator: int,
    denominator: int,
    emission_rate: int,
    amount_staked: int,
    last_update_time,
    current_time_ms: int,
) -> Fraction:
    cumulative_reward_per_token = Fraction(numerator, denominator)
    if amount_staked == 0:
        return cumulative_reward_per_token

    elapsed_time_ms = current_time_ms - _datetime_to_posix_ms(last_update_time)
    if elapsed_time_ms <= 0:
        return cumulative_reward_per_token

    return cumulative_reward_per_token + Fraction(
        emission_rate * elapsed_time_ms,
        amount_staked * MILLIS_IN_DAY,
    )


def query_staking_positions_per_wallet(
    wallet: str,
):
    current_time_ms = int(datetime.now().timestamp() * 1000)
    cursor = sqlite_db.execute_sql(
        """
        WITH latest_farmparams AS (
            SELECT
                fp.*,
                ROW_NUMBER() OVER (
                    PARTITION BY fp.pool_id
                    ORDER BY fp.last_update_time DESC
                ) AS rn
            FROM farmparams fp
        )
        SELECT
            sp.pool_id,
            sp.staked_since,
            sp.batching_output_index,
            a.address_raw,
            scprs.cumulative_pool_rpts_at_start_numerator,
            scprs.cumulative_pool_rpts_at_start_denominator,
            txo.transaction_hash,
            txo.output_index,
            tk.policy_id AS stake_token_policy_id,
            tk.asset_name AS stake_token_asset_name,
            txov.amount AS position_size,
            rtk.policy_id AS reward_token_policy_id,
            rtk.asset_name AS reward_token_asset_name,
            frt.idx AS reward_token_index,
            fer.emission_rate,
            fcrpt.cumulative_reward_per_token_numerator,
            fcrpt.cumulative_reward_per_token_denominator,
            fp.last_update_time,
            fp.amount_staked
        FROM stakingparams sp
        JOIN address a ON sp.owner_id = a.id
        JOIN stakingcumulativepoolrptsatstart scprs ON scprs.staking_params_id = sp.id
        JOIN stakingstate ss ON ss.staking_params_id = sp.id
        JOIN transactionoutput txo ON ss.transaction_output_id = txo.id
        LEFT JOIN latest_farmparams fp ON fp.pool_id = sp.pool_id AND fp.rn = 1
        LEFT JOIN token tk ON fp.stake_token_id = tk.id
        LEFT JOIN farmrewardtoken frt
          ON frt.farm_params_id = fp.id
         AND frt.idx = scprs."index"
        LEFT JOIN token rtk ON frt.token_id = rtk.id
        LEFT JOIN farmemissionrate fer
          ON fer.farm_params_id = fp.id
         AND fer.idx = scprs."index"
        LEFT JOIN farmcumulativerewardpertoken fcrpt
          ON fcrpt.farm_params_id = fp.id
         AND fcrpt.idx = scprs."index"
        LEFT JOIN transactionoutputvalue txov
          ON txov.transaction_output_id = txo.id
         AND txov.token_id = tk.id
        WHERE a.address_raw = ?
          AND txo.spent_in_block_id IS NULL
        ORDER BY sp.staked_since ASC, sp.batching_output_index ASC
        """,
        (wallet,),
    )
    results = []
    for row in cursor.fetchall():
        position_size = row[10] or 0
        earned_rewards = []
        if all(value is not None for value in row[11:19]):
            start_cumulative_reward_per_token = Fraction(row[4], row[5])
            current_cumulative_reward_per_token = _project_cumulative_rewards_per_token(
                numerator=row[15],
                denominator=row[16],
                emission_rate=row[14],
                amount_staked=row[18],
                last_update_time=row[17],
                current_time_ms=current_time_ms,
            )
            earned_amount = _floor_scale_fraction(
                current_cumulative_reward_per_token, position_size
            ) - _floor_scale_fraction(start_cumulative_reward_per_token, position_size)
            earned_rewards.append(
                {
                    "policy_id": row[11],
                    "asset_name": row[12],
                    "amount": earned_amount,
                    "idx": row[13],
                }
            )
        results.append(
            {
                "pool_id": row[0],
                "staked_since": row[1],
                "batching_output_index": row[2],
                "address": row[3],
                "cumulative_pool_rpts_at_start": {
                    "numerator": row[4],
                    "denominator": row[5],
                },
                "utxo_tx_hash": row[6],
                "utxo_tx_index": row[7],
                "stake_token": {
                    "policy_id": row[8],
                    "asset_name": row[9],
                },
                "position_size": position_size,
                "earned_rewards": earned_rewards,
            }
        )
    return results
