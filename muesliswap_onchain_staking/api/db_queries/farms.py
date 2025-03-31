from ..db_models import sqlite_db

def query_farms():
    cursor = sqlite_db.execute_sql(
        """
        SELECT
        fp.pool_id,
        tk2.policy_id as stake_token_policy_id,
        tk2.asset_name as stake_token_asset_name,
        fp.farm_type,
        fp.last_update_time,
        fp.amount_staked,
        group_concat(tk.policy_id, ';') as reward_token_policy_id,
        group_concat(tk.asset_name, ';') as reward_token_asset_name,
        group_concat(frt.idx, ';') as reward_token_index,
        group_concat(fer.emission_rate, ';'),
        group_concat(fer.idx, ';'),
        group_concat(fcrpt.cumulative_reward_per_token_numerator, ';'),
        group_concat(fcrpt.cumulative_reward_per_token_denominator, ';'),
        group_concat(fcrpt.idx, ';')
        FROM
        farmstate fs
        JOIN farmparams fp ON fs.farm_params_id = fp.id
        JOIN farmrewardtoken frt ON frt.farm_params_id = fp.id
        JOIN token tk on frt.token_id = tk.id
        JOIN farmemissionrate fer ON fer.farm_params_id = fp.id
        JOIN farmcumulativerewardpertoken fcrpt ON fcrpt.farm_params_id = fp.id
        JOIN token tk2 on fp.stake_token_id = tk2.id
        GROUP BY fs.farm_params_id
        """
    )
    results = []
    for row in cursor.fetchall():
        results.append(
            {
                "pool_id": row[0],
                "stake_token": {
                    "policy_id": row[1],
                    "asset_name": row[2],
                },
                "farm_type": row[3],
                "last_update_time": row[4],
                "amount_staked": row[5],
                "reward_tokens": [
                    {
                        "policy_id": policy_id,
                        "asset_name": asset_name,
                        "idx": idx,
                    }
                    for policy_id, asset_name, idx in zip(
                        row[6].split(";"),
                        row[7].split(";"),
                        row[8].split(";"),
                    )
                ],
                "emission_rates": [
                    {
                        "emission_rate": emission_rate,
                        "idx": idx,
                    }
                    for emission_rate, idx in zip(
                        row[9].split(";"),
                        row[10].split(";"),
                    )
                ],
                "cumulative_rewards_per_token": [
                    {
                        "numerator": numerator,
                        "denominator": denominator,
                        "idx": idx,
                    }
                    for numerator, denominator, idx in zip(
                        row[11].split(";"),
                        row[12].split(";"),
                        row[13].split(";"),
                    )
                ],
            }
        )
    return results
