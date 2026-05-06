import logging
from copy import deepcopy
from contextlib import asynccontextmanager
from typing import Any, Optional, List, Tuple
from pydantic import BaseModel, Field

from fastapi import Query, FastAPI, HTTPException
from pycardano.exception import UTxOSelectionException
from pycardano.exception import TransactionFailedException
from fastapi.responses import ORJSONResponse
from starlette.responses import Response
from fastapi_cache import FastAPICache, Coder
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi.middleware.cors import CORSMiddleware
from pycardano.backend.blockfrost import BlockFrostChainContext
from pycardano import Network

from muesliswap_onchain_staking.api.db_models import db

from muesliswap_onchain_staking.api.db_queries import *
from muesliswap_onchain_staking.api.tx_builder.build import (
    place_stake_order,
    place_unstake_order,
    cancel_order,
    mint_farm_token,
)
from muesliswap_onchain_staking.api.ep_util import get_body_or_query_params
from muesliswap_onchain_staking.onchain import batching
from muesliswap_onchain_staking.secret import BLOCKFROST_PROJECT_ID
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
from muesliswap_onchain_staking.utils.from_script_context import from_address


# logger setup
_LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s", level=logging.INFO, force=True
)


def DashingQuery(convert_underscores=True, **kwargs) -> Query:
    """
    Enable underscore-to-hyphen aliasing for query parameters by default.
    """
    query = Query(**kwargs)
    query.convert_underscores = convert_underscores
    return query


app = FastAPI(
    default_response_class=ORJSONResponse,
    title="MuesliSwap Staking API",
    description="The MuesliSwap Staking API provides access to on-chain data for the MuesliSwap On-Chain Staking System.",
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


def decode_token_name(token_name_hex: str) -> str | None:
    if token_name_hex == "":
        return ""
    try:
        return bytes.fromhex(token_name_hex).decode("utf-8")
    except ValueError:
        return None
    except UnicodeDecodeError:
        return None


HEX_RE = r"^[0-9a-fA-F]+$"
HEX_56_RE = r"^[0-9a-fA-F]{56}$"
HEX_64_RE = r"^[0-9a-fA-F]{64}$"
PUBKEY_HASHES_RE = r"^[0-9a-fA-F]{56}(?:,[0-9a-fA-F]{56})*$"
TOKEN_RE = r"^(\.|[0-9a-fA-F]{56}\.[0-9a-fA-F]*)$"
AS_BASE_RE = r"^(from|to)$"
BOOLISH_RE = r"^(true|false|1|0)$"
PROVIDER_RE = r"^(muesliswap|minswap|vyfi)$"
PROPOSAL_TYPE_RE = r"^(any|[A-Za-z]+(?:,[A-Za-z]+)*)$"


#################################################################################################
#                                            Endpoints                                          #
#################################################################################################

PolicyIdQuery = DashingQuery(
    description="Policy ID of a token",
    examples=["", "afbe91c0b44b3040e360057bf8354ead8c49c4979ae6ab7c4fbdc9eb"],
    pattern=HEX_56_RE,
)
TokenNameQuery = DashingQuery(
    description="Hex encoded name of a token",
    examples=["", "4d494c4b7632"],
    pattern=HEX_RE,
)
AsBaseQuery = DashingQuery(
    description="Token that should be used as base",
    examples=["from", "to"],
    pattern=AS_BASE_RE,
)
IncludeTradesQuery = DashingQuery(
    description="Whether or not to include the last trades data",
    examples=["true", "false"],
    pattern=BOOLISH_RE,
)
IncludeAdaPricesQuery = DashingQuery(
    description="Whether or not to include the ada price data",
    examples=["true", "false"],
    pattern=BOOLISH_RE,
)
VerifiedQuery = DashingQuery(
    description="Filter for only verified tokens",
    examples=["true", "false", "1", "0"],
    pattern=BOOLISH_RE,
)
PubkeyHashQuery = DashingQuery(
    description="Public key hash of a wallet",
    examples=["dcbc64ce3cc4aeac225a45dd67dfc3717f732f6303556efb6dd8024f"],
    pattern=HEX_56_RE,
)
StakekeyHashQuery = DashingQuery(
    description="Stake key hash of a wallet",
    examples=["dcbc64ce3cc4aeac225a45dd67dfc3717f732f6303556efb6dd8024f"],
    pattern=HEX_56_RE,
)
PubkeyHashesQuery = DashingQuery(
    description="Comma-separated public key hashes",
    examples=[
        "",
        "dcbc64ce3cc4aeac225a45dd67dfc3717f732f6303556efb6dd8024f,dcbc64ce3cc4aeac225a45dd67dfc3717f732f6303556efb6dd8024f",
    ],
    pattern=PUBKEY_HASHES_RE,
)
WalletQuery = DashingQuery(
    description="Wallet address in hex",
    examples=[
        "01dcbc64ce3cc4aeac225a45dd67dfc3717f732f6303556efb6dd8024f0420b0d045f11e8a66319f9d19ffcba35aa9fee0164014776a1f7c95"
    ],
    min_length=2,
    pattern=HEX_RE,
)
AddressQuery = DashingQuery(
    description="Wallet address in bech32",
    examples=[
        "addr1q8wtcexw8nz2atpztfza6e7lcdch7ue0vvp42mhmdhvqyncyyzcdq303r69xvvvln5vlljart25lacqkgq28w6sl0j2skvlxf4"
    ],
    pattern=r"^(addr|addr_test)1[0-9a-z]+$",
)
ProviderQuery = DashingQuery(
    description="Provider name",
    examples=["muesliswap", "minswap", "vyfi"],
    pattern=PROVIDER_RE,
)
TokenQuery = DashingQuery(
    description="Token name in hex",
    examples=[
        ".",
        "afbe91c0b44b3040e360057bf8354ead8c49c4979ae6ab7c4fbdc9eb.4d494c4b7632",
    ],
    pattern=TOKEN_RE,
)
AssetIdentifierQuery = DashingQuery(
    description="Asset identifier in hex: concatenation of the policy_id and hex-encoded asset_name",
    examples=[
        "",
        "afbe91c0b44b3040e360057bf8354ead8c49c4979ae6ab7c4fbdc9eb4d494c4b7632",
    ],
    min_length=56,
    pattern=HEX_RE,
)
TransactionHashQuery = DashingQuery(
    description="Transaction hash",
    examples=["6804edf9712d2b619edb6ac86861fe93a730693183a262b165fcc1ba1bc99cad"],
    pattern=HEX_64_RE,
)
TransactionIdQuery = DashingQuery(
    description="Transaction ID",
    examples=[0, 1, 2],
    ge=0,
)
ProposalTypeQuery = DashingQuery(
    description="Proposal types (e.g. Opinion, Reject, GovStateUpdate, FundPayout, LicenseRelease, PoolUpgrade) that must be contained, separated through ','",
    examples=[["any"], ["FundPayout"], ["LicenseRelease", "PoolUpgrade"]],
    default="any",
    pattern=PROPOSAL_TYPE_RE,
)

class StakeOrderRequest(BaseModel):
    user_address: str
    stake_token: str
    stake_amount: int
    pool_id: str


class UnstakeOrderRequest(BaseModel):
    user_address: str
    staking_position_tx_hash: str
    staking_position_tx_index: int


class CancelOrderRequest(BaseModel):
    user_address: str
    order_tx_hash: str
    order_tx_index: int


class MintFarmTokenRequest(BaseModel):
    user_address: str
    pool_id: str
    amount: int = Field(gt=0)


OrderLimitQuery = DashingQuery(
    description="Maximum number of results to return",
    examples=[25],
    default=50,
    ge=1,
    le=200,
)

OrderOffsetQuery = DashingQuery(
    description="Offset into the result set",
    examples=[0],
    default=0,
    ge=0,
)

IncludePositionDetailsQuery = DashingQuery(
    description="Whether to enrich orders with matching staking position details",
    examples=["true", "false"],
    default="true",
    pattern=BOOLISH_RE,
)


def _bytes_to_hex(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    # pycardano/waswo objects sometimes store raw bytes under common fields
    for attr in ["payload", "value", "bytes", "tx_id"]:
        raw = getattr(value, attr, None)
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw).hex()
    # opshin TxId often supports to_primitive() -> bytes
    to_primitive = getattr(value, "to_primitive", None)
    if callable(to_primitive):
        raw = to_primitive()
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw).hex()
    return None


def _tx_out_ref_to_json(ref: Any) -> dict[str, Any] | None:
    """
    Convert an on-chain `TxOutRef` (as present in the batching contract datum)
    into JSON-friendly `{utxo_tx_hash, utxo_tx_index}`.
    """
    tx_index = None
    for attr in ["index", "tx_index", "output_index", "out_index", "idx"]:
        value = getattr(ref, attr, None)
        if value is not None:
            tx_index = value
            break

    tx_id_obj = (
        getattr(ref, "id", None)
        or getattr(ref, "txid", None)
        or getattr(ref, "tx_id", None)
        or getattr(ref, "transaction_id", None)
    )
    tx_hash_hex = _bytes_to_hex(tx_id_obj)
    if tx_hash_hex is None or tx_index is None:
        return None

    return {"utxo_tx_hash": tx_hash_hex.lower(), "utxo_tx_index": int(tx_index)}


def _opshin_address_to_hex(addr: Any) -> str | None:
    """
    Convert an opshin `Address` (datum field) to the API's `user_address` format:
    hex-encoded `pycardano.Address.to_primitive()`.
    """
    try:
        pycardano_addr = from_address(addr)
    except Exception:
        return None

    to_prim = getattr(pycardano_addr, "to_primitive", None)
    if not callable(to_prim):
        return None
    prim = to_prim()
    if isinstance(prim, bytes):
        return prim.hex().lower()
    if isinstance(prim, str):
        # Some implementations might return a hex string already.
        return prim.lower()
    try:
        return bytes(prim).hex().lower()
    except Exception:
        return None


def _parse_boolish(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise HTTPException(
        status_code=422,
        detail=f"Invalid boolean value '{value}'. Use true/false/1/0.",
    )


# Blockfrost chain context for listing UTxOs at the batching contract.
_blockfrost_context = BlockFrostChainContext(
    project_id=BLOCKFROST_PROJECT_ID,
    network=Network.TESTNET,
)
_, _, _batching_address = get_contract(module_name(batching), compressed=True)


@app.get("/api/v1/health")
def health(response: Response):
    add_cachecontrol(response, max_age=5)
    add_jsoncontenttype(response)
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
def farms(response: Response, include_decoded_names: bool = Query(default=False)):
    """
    Get all farms.
    """
    add_cachecontrol(response, max_age=20)
    add_jsoncontenttype(response)
    farms_data = query_farms()
    if not include_decoded_names:
        return ORJSONResponse(farms_data)

    farms_data_with_decoded_names = deepcopy(farms_data)
    for farm in farms_data_with_decoded_names:
        farm["stake_token"]["decoded_asset_name"] = decode_token_name(
            farm["stake_token"]["asset_name"]
        )
        for reward_token in farm["reward_tokens"]:
            reward_token["decoded_asset_name"] = decode_token_name(
                reward_token["asset_name"]
            )
    return ORJSONResponse(farms_data_with_decoded_names)


@app.get("/api/v1/staking/positions")
def staking_positions(response: Response, wallet: str = WalletQuery):
    """
    Get all staking positions for a wallet.
    """
    add_cachecontrol(response, max_age=10)
    add_jsoncontenttype(response)
    positions = query_staking_positions_per_wallet(wallet)
    if not positions:
        return ORJSONResponse(
            {
                "items": [],
                "count": 0,
                "message": "No staking positions found for this wallet.",
            }
        )
    return ORJSONResponse({"items": positions, "count": len(positions)})


@app.get("/api/v1/orders")
def orders(
    response: Response,
    wallet: Optional[str] = Query(default=None),
    user_address: Optional[str] = Query(default=None),
    limit: int = OrderLimitQuery,
    offset: int = OrderOffsetQuery,
    include_position_details: Optional[str] = Query(default=None),
    include_position_details_dashed: Optional[str] = Query(
        default=None, alias="include-position-details"
    ),
):
    """
    Get pending unstake orders for a wallet.

    Pending means: the `UnstakeOrder` datum is currently present in the batching contract.
    """
    add_cachecontrol(response, max_age=5)
    add_jsoncontenttype(response)

    # Backward compatibility for frontend parameter naming:
    # - legacy: `wallet`
    # - new: `user_address`
    resolved_user_address = user_address or wallet
    if not resolved_user_address:
        raise HTTPException(
            status_code=422,
            detail="Missing wallet address. Provide either 'wallet' or 'user_address'.",
        )

    if not isinstance(resolved_user_address, str) or not resolved_user_address:
        raise HTTPException(status_code=422, detail="Invalid wallet address.")

    if not all(c in "0123456789abcdefABCDEF" for c in resolved_user_address):
        raise HTTPException(status_code=422, detail="Wallet/user_address must be hex.")

    include_position_details_flag = _parse_boolish(
        include_position_details
        if include_position_details is not None
        else include_position_details_dashed,
        default=True,
    )

    user_address_lower = resolved_user_address.lower()

    position_by_ref: dict[Tuple[str, int], dict[str, Any]] = {}
    if include_position_details_flag:
        for p in query_staking_positions_per_wallet(resolved_user_address):
            position_by_ref[(p["utxo_tx_hash"], int(p["utxo_tx_index"]))] = p

    items: list[dict[str, Any]] = []
    batching_utxos = _blockfrost_context.utxos(_batching_address)
    for u in batching_utxos:
        if not u.output.datum:
            continue
        try:
            order_datum = batching.UnstakeOrder.from_cbor(u.output.datum.cbor)
        except Exception:
            # Batching address contains mixed order types; only process UnstakeOrder here.
            continue

        owner_hex = _opshin_address_to_hex(order_datum.owner)
        if owner_hex != user_address_lower:
            continue

        staking_position_ref = _tx_out_ref_to_json(order_datum.staking_position)
        if staking_position_ref is None:
            # If we cannot decode it reliably, skip the entry to avoid returning unusable data.
            continue

        order_tx_hash = u.input.transaction_id.payload.hex().lower()
        order_tx_index = int(u.input.index)

        item: dict[str, Any] = {
            "order_type": "unstake",
            "order_tx_hash": order_tx_hash,
            "order_tx_index": order_tx_index,
            "owner_address": owner_hex,
            "staking_position": staking_position_ref,
        }

        if include_position_details_flag:
            key = (staking_position_ref["utxo_tx_hash"], staking_position_ref["utxo_tx_index"])
            position = position_by_ref.get(key)
            item["staking_position_details"] = position if position is not None else None

        items.append(item)

    # Stable ordering for paging.
    items.sort(key=lambda it: (it["order_tx_hash"], it["order_tx_index"]))

    total = len(items)
    page = items[offset : offset + limit]

    return ORJSONResponse(
        {
            "items": page,
            "count": total,
            "offset": offset,
            "limit": limit,
        }
    )


@app.post("/api/v1/stake_order")
async def stake_order(
    params: StakeOrderRequest = get_body_or_query_params(
        StakeOrderRequest,
        required_query_params=[
            "user_address",
            "stake_token",
            "stake_amount",
            "pool_id",
        ],
    ),
):
    """
    Place a stake order.
    """
    try:
        tx_cbor = await place_stake_order(
            user_address=params.user_address,
            stake_token_str=params.stake_token,
            stake_amount=params.stake_amount,
            pool_id_str=params.pool_id,
        )
    except (ValueError, UTxOSelectionException, TransactionFailedException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ORJSONResponse({"tx_cbor": tx_cbor})


@app.post("/api/v1/unstake_order")
async def unstake_order(
    params: UnstakeOrderRequest = get_body_or_query_params(
        UnstakeOrderRequest,
        required_query_params=[
            "user_address",
            "staking_position_tx_hash",
            "staking_position_tx_index",
        ],
    ),
):
    """
    Place an unstake order for an existing staking position.

    Provide the UTxO reference of the staking position (available from
    GET /api/v1/staking/positions as utxo_tx_hash / utxo_tx_index).
    """
    try:
        tx_cbor = await place_unstake_order(
            user_address=params.user_address,
            staking_position_tx_hash=params.staking_position_tx_hash,
            staking_position_tx_index=params.staking_position_tx_index,
        )
    except (ValueError, UTxOSelectionException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ORJSONResponse({"tx_cbor": tx_cbor})


@app.post("/api/v1/cancel_order")
async def cancel_order_endpoint(
    params: CancelOrderRequest = get_body_or_query_params(
        CancelOrderRequest,
        required_query_params=[
            "user_address",
            "order_tx_hash",
            "order_tx_index",
        ],
    ),
):
    """
    Cancel a pending stake or unstake order sitting in the batching contract.

    Provide the UTxO reference of the order to cancel.
    """
    try:
        tx_cbor = await cancel_order(
            user_address=params.user_address,
            order_tx_hash=params.order_tx_hash,
            order_tx_index=params.order_tx_index,
        )
    except (ValueError, UTxOSelectionException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ORJSONResponse({"tx_cbor": tx_cbor})


@app.post("/api/v1/mint_farm_token")
async def mint_farm_token_endpoint(
    params: MintFarmTokenRequest = get_body_or_query_params(
        MintFarmTokenRequest,
        required_query_params=[
            "user_address",
            "pool_id",
            "amount",
        ],
    ),
):
    """
    Mint the stake token configured for a farm.
    """
    stake_token = query_farm_stake_token(params.pool_id)
    if stake_token is None:
        raise HTTPException(status_code=404, detail="Farm not found for provided pool_id")

    farm_token = (
        f"{stake_token['policy_id']}."
        f"{stake_token['asset_name']}"
    )

    try:
        tx_cbor = await mint_farm_token(
            user_address=params.user_address,
            farm_token_str=farm_token,
            amount=params.amount,
        )
    except (ValueError, UTxOSelectionException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ORJSONResponse(
        {
            "pool_id": params.pool_id,
            "minted_token": farm_token,
            "amount": params.amount,
            "tx_cbor": tx_cbor,
        }
    )


# for debugging
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app", host="localhost", port=8008, log_level="info", reload=True
    )
