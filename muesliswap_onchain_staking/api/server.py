import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Query, FastAPI
from fastapi.responses import ORJSONResponse
from starlette.responses import Response
from fastapi_cache import FastAPICache, Coder
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi.middleware.cors import CORSMiddleware

from muesliswap_onchain_staking.api.db_models import db

from muesliswap_onchain_staking.api.db_queries import *

# logger setup
_LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s", level=logging.INFO, force=True
)


def DashingQuery(convert_underscores=True, **kwargs) -> Query:
    """
    This class enables "convert underscores" by default, allowing parameter names
    with underscores to be accessed via hypehenated versions
    """
    query = Query(**kwargs)
    query.convert_underscores = convert_underscores
    return query


app = FastAPI(
    default_response_class=ORJSONResponse,
    title="MuesliSwap Staking API.",
    description="The MuesliSwap Staking API provides access to on-chain data for the MuesliSwap Onchain Staking System.",
    version="0.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NoCoder(Coder):
    @classmethod
    def encode(cls, value: Any) -> str:
        return value

    @classmethod
    def decode(cls, value: str) -> Any:
        return value


@asynccontextmanager
async def startup():
    # For now in memory, but we can use redis or other backends later
    FastAPICache.init(
        InMemoryBackend(),
        expire=20,
        coder=NoCoder,
    )
    yield


def add_cachecontrol(response: Response, max_age: int, directive: str = "public"):
    # see https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
    # and https://fastapi.tiangolo.com/advanced/response-headers/
    response.headers["Cache-Control"] = f"{directive}, max-age={max_age}"


def add_jsoncontenttype(response: Response):
    # see https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
    # and https://fastapi.tiangolo.com/advanced/response-headers/
    response.headers["Content-Type"] = f"application/json"


#################################################################################################
#                                            Endpoints                                          #
#################################################################################################

PolicyIdQuery = DashingQuery(
    description="Policy ID of a token",
    examples=["", "afbe91c0b44b3040e360057bf8354ead8c49c4979ae6ab7c4fbdc9eb"],
    # TODO add validation
)
TokenNameQuery = DashingQuery(
    description="Hex encoded name of a token",
    examples=["", "4d494c4b7632"],
    # TODO add validation
)
AsBaseQuery = DashingQuery(
    description="Token that should be used as base",
    examples=["from", "to"],
    # TODO add validation
)
IncludeTradesQuery = DashingQuery(
    description="Whether or not to include the last trades data",
    examples=["true", "false"],
    # TODO add validation
)
IncludeAdaPricesQuery = DashingQuery(
    description="Whether or not to include the ada price data",
    examples=["true", "false"],
    # TODO add validation
)
VerifiedQuery = DashingQuery(
    description="Filter for only verified tokens",
    examples=["true", "false", "1", "0"],
    # TODO add validation
)
PubkeyHashQuery = DashingQuery(
    description="Pubkeyhash of a wallet",
    examples=["dcbc64ce3cc4aeac225a45dd67dfc3717f732f6303556efb6dd8024f"],
    # TODO add validation
)
StakekeyHashQuery = DashingQuery(
    description="Stake key hash of a wallet",
    examples=["dcbc64ce3cc4aeac225a45dd67dfc3717f732f6303556efb6dd8024f"],
    # TODO add validation
)
PubkeyHashesQuery = DashingQuery(
    description="Stake key hash of a wallet",
    examples=[
        "",
        "dcbc64ce3cc4aeac225a45dd67dfc3717f732f6303556efb6dd8024f,dcbc64ce3cc4aeac225a45dd67dfc3717f732f6303556efb6dd8024f",
    ],
    # TODO add validation
)
WalletQuery = DashingQuery(
    description="Wallet address in hex",
    examples=[
        "01dcbc64ce3cc4aeac225a45dd67dfc3717f732f6303556efb6dd8024f0420b0d045f11e8a66319f9d19ffcba35aa9fee0164014776a1f7c95"
    ],
    # TODO add validation
)
AddressQuery = DashingQuery(
    description="Wallet address in bech32",
    examples=[
        "addr1q8wtcexw8nz2atpztfza6e7lcdch7ue0vvp42mhmdhvqyncyyzcdq303r69xvvvln5vlljart25lacqkgq28w6sl0j2skvlxf4"
    ],
    # TODO add validation
)
ProviderQuery = DashingQuery(
    description="Provider name",
    examples=["muesliswap", "minswap", "vyfi"],
    # TODO add validation
)
TokenQuery = DashingQuery(
    description="Toke name in hex",
    examples=[
        ".",
        "afbe91c0b44b3040e360057bf8354ead8c49c4979ae6ab7c4fbdc9eb.4d494c4b7632",
    ],
    # TODO add validation
)
AssetIdentifierQuery = DashingQuery(
    description="Asset identifier in hex: Concatenation of the policy_id and hex-encoded asset_name",
    examples=[
        "",
        "afbe91c0b44b3040e360057bf8354ead8c49c4979ae6ab7c4fbdc9eb4d494c4b7632",
    ],
    # TODO add validation
)
TransactionHashQuery = DashingQuery(
    description="Transaction hash",
    examples=["6804edf9712d2b619edb6ac86861fe93a730693183a262b165fcc1ba1bc99cad"],
    # TODO add validation
)
TransactionIdQuery = DashingQuery(
    description="Transaction id",
    examples=[0, 1, 2],
    # TODO add validation
)
ProposalTypeQuery = DashingQuery(
    description="Proposal types (e.g. Opinion, Reject, GovStateUpdate, FundPayout, LicenseRelease, PoolUpgrade) that must be contained, separated through ','",
    examples=[["any"], ["FundPayout"], ["LicenseRelease", "PoolUpgrade"]],
    default="any",
    # TODO add validation
)


@app.get("/api/v1/health")
def health():
    last_block = db.Block.select().order_by(db.Block.slot.desc()).first()
    return ORJSONResponse(
        {
            "status": "ok" if last_block else "nok",
            "last_block": (
                {
                    "slot": last_block.slot,
                    "height": last_block.height,
                    "hash": last_block.hash,
                }
                if last_block
                else None
            ),
        }
    )


@app.get("/api/v1/farms")
def farms():
    """
    Get all farms.
    """
    return ORJSONResponse(query_farms())


# for debugging
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app", host="localhost", port=8001, log_level="info", reload=True
    )
