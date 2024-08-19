from .db import (
    Block,
    Address,
    Datum,
    Token,
    AssetName,
    PolicyId,
    Transaction,
    TransactionOutput,
    TransactionOutputValue,
    sqlite_db,
)
from .staking import (
    StakingParams,
    StakingState,
    StakingCumulativePoolRptsAtStart,
)
from .farms import (
    FarmState,
    FarmParams,
    FarmRewardToken,
    FarmEmissionRate,
    FarmCumulativeRewardPerToken,
)

sqlite_db.connect()
sqlite_db.create_tables(
    [
        Block,
        Address,
        Datum,
        Token,
        Transaction,
        TransactionOutput,
        TransactionOutputValue,
        StakingParams,
        StakingState,
        StakingCumulativePoolRptsAtStart,
        FarmState,
        FarmParams,
        FarmRewardToken,
        FarmEmissionRate,
        FarmCumulativeRewardPerToken,
    ]
)
