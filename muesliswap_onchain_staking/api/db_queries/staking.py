from ..db_models import sqlite_db


def query_staking_positions_per_wallet(
    wallet: str,
):
    cursor = sqlite_db.execute_sql(
        """
        SELECT
        sp.pool_id,
        sp.staked_since,
        sp.batching_output_index,
        a.address_raw,
        scprs.cumulative_pool_rpts_at_start_numerator,
        scprs.cumulative_pool_rpts_at_start_denominator
        FROM
        stakingparams sp
        JOIN address a ON sp.owner_id = a.id
        JOIN stakingcumulativepoolrptsatstart scprs ON scprs.staking_params_id = sp.id
        JOIN stakingstate ss ON ss.staking_params_id = sp.id
        WHERE a.address_raw = ?
        """,
        (wallet,),
    )
    results = []
    for row in cursor.fetchall():
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
            }
        )
    return results
