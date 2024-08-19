from .db import *


class StakingParams(BaseModel):
    owner = ForeignKeyField(Address, backref="staking_params")
    pool_id = ForeignKeyField(AssetName(), backref="staking_params")
    staked_since = DateTimeField()
    batching_output_index = IntegerField()


class StakingCumulativePoolRptsAtStart(BaseModel):
    staking_params = ForeignKeyField(
        StakingParams, backref="staking_cumulative_pool_rpts_at_start"
    )
    cumulative_pool_rpts_at_start_numerator = IntegerField()
    cumulative_pool_rpts_at_start_denominator = IntegerField()
    index = IntegerField()


class StakingState(OutputStateModel):
    staking_params = ForeignKeyField(StakingParams, backref="staking_states")
