from .db import *


class FarmParams(BaseModel):
    pool_id = AssetName()
    stake_token = ForeignKeyField(Token, backref="farm_params")
    farm_type = CharField(max_length=64)
    last_update_time = DateTimeField()
    amount_staked = IntegerField()


class FarmRewardToken(BaseModel):
    farm_params = ForeignKeyField(
        FarmParams, backref="farm_reward_tokens", on_delete="CASCADE"
    )
    token = ForeignKeyField(Token, backref="farm_reward_tokens")
    idx = IntegerField()


class FarmEmissionRate(BaseModel):
    farm_params = ForeignKeyField(
        FarmParams, backref="farm_emission_rates", on_delete="CASCADE"
    )
    emission_rate = IntegerField()
    idx = IntegerField()


class FarmCumulativeRewardPerToken(BaseModel):
    farm_params = ForeignKeyField(
        FarmParams, backref="farm_cumulative_rewards_per_token", on_delete="CASCADE"
    )
    cumulative_reward_per_token_numerator = IntegerField()
    cumulative_reward_per_token_denominator = IntegerField()
    idx = IntegerField()


class FarmState(OutputStateModel):
    farm_params = ForeignKeyField(FarmParams, backref="farm_states")
