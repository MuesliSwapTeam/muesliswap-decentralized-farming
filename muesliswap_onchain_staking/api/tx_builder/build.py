from muesliswap_onchain_staking.onchain import batching, staking
from muesliswap_onchain_staking.onchain import unstake_permission_nft as unstake_permission_nft_contract
from muesliswap_onchain_staking.onchain.util import unstake_permission_nft_token_name
from muesliswap_onchain_staking.utils.network import context
from muesliswap_onchain_staking.utils import to_address, to_tx_out_ref
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name
from muesliswap_onchain_staking.offchain.util import (
    asset_from_token,
    with_min_lovelace,
)
from pycardano import (
    Transaction,
    TransactionBuilder,
    TransactionId,
    TransactionInput,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
    TransactionOutput,
    Value,
    Address,
    Redeemer,
    AssetName,
    Asset,
    MultiAsset,
    ExecutionUnits,
    Network,
)
from pycardano.backend.blockfrost import BlockFrostChainContext
from pycardano.exception import TransactionFailedException
from opshin.prelude import Token
from muesliswap_onchain_staking.offchain.util import token_from_string
from muesliswap_onchain_staking.secret import BLOCKFROST_PROJECT_ID

_blockfrost_context = BlockFrostChainContext(
    project_id=BLOCKFROST_PROJECT_ID,
    network=Network.TESTNET,
)


async def place_stake_order(
    user_address: Address,
    stake_token_str: str,
    stake_amount: int,
    pool_id_str: str,
):
    stake_token = token_from_string(stake_token_str)
    pool_id = token_from_string("." + pool_id_str).token_name

    _, _, stake_order_batching = get_contract(module_name(batching), compressed=True)

    stake_order_datum = batching.StakeOrder(
        owner=to_address(Address.from_primitive(user_address)),
        pool_id=pool_id,
    )

    builder = TransactionBuilder(_blockfrost_context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Create Add Stake Order"]}})
        )
    )
    builder.add_input_address(user_address)

    stake_order_output = TransactionOutput(
        address=stake_order_batching,
        amount=Value(
            multi_asset=asset_from_token(stake_token, stake_amount),
        ),
        datum=stake_order_datum,
    )

    builder.add_output(with_min_lovelace(stake_order_output, _blockfrost_context))
    builder.ttl = _blockfrost_context.last_block_slot + 100

    tx_body = builder.build(change_address=user_address)
    transaction = Transaction(
        transaction_body=tx_body,
        transaction_witness_set=builder.build_witness_set(),
        auxiliary_data=builder.auxiliary_data,
    )

    return transaction.to_cbor_hex()


async def place_unstake_order(
    user_address: Address,
    staking_position_tx_hash: str,
    staking_position_tx_index: int,
):
    _, _, stake_order_batching = get_contract(module_name(batching), compressed=True)
    unstake_permission_nft_script, unstake_permission_nft_pid, _ = get_contract(
        module_name(unstake_permission_nft_contract), compressed=True
    )

    staking_position_ref = to_tx_out_ref(
        TransactionInput(
            transaction_id=TransactionId(bytes.fromhex(staking_position_tx_hash)),
            index=staking_position_tx_index,
        )
    )

    user_addr_obj = Address.from_primitive(user_address)
    unstake_order_datum = batching.UnstakeOrder(
        owner=to_address(user_addr_obj),
        staking_position=staking_position_ref,
    )
    # Same type — batching_types.UnstakeOrder is shared between batching and
    # unstake_permission_nft modules via star imports.
    permission_nft_redeemer = batching.UnstakeOrder(
        owner=unstake_order_datum.owner,
        staking_position=unstake_order_datum.staking_position,
    )

    permission_nft_token = Token(
        policy_id=unstake_permission_nft_pid.payload,
        token_name=unstake_permission_nft_token_name(permission_nft_redeemer),
    )
    permission_nft_asset = asset_from_token(permission_nft_token, 1)

    stake_order_output = TransactionOutput(
        address=stake_order_batching,
        amount=Value(multi_asset=permission_nft_asset),
        datum=unstake_order_datum,
    )

    builder = TransactionBuilder(_blockfrost_context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Place Unstake Order"]}})
        )
    )
    builder.add_input_address(user_address)
    builder.add_output(with_min_lovelace(stake_order_output, _blockfrost_context))
    builder.ttl = _blockfrost_context.last_block_slot + 179
    builder.mint = permission_nft_asset
    builder.add_minting_script(
        unstake_permission_nft_script,
        Redeemer(permission_nft_redeemer),
    )

    tx_body = builder.build(change_address=user_address)
    transaction = Transaction(
        transaction_body=tx_body,
        transaction_witness_set=builder.build_witness_set(),
        auxiliary_data=builder.auxiliary_data,
    )

    return transaction.to_cbor_hex()


async def cancel_order(
    user_address: Address,
    order_tx_hash: str,
    order_tx_index: int,
):
    batching_script, _, batching_address = get_contract(
        module_name(batching), compressed=True
    )

    batching_utxos = _blockfrost_context.utxos(batching_address)
    utxo_to_cancel = next(
        (
            u for u in batching_utxos
            if u.input.transaction_id.payload.hex() == order_tx_hash.lower()
            and u.input.index == order_tx_index
        ),
        None,
    )
    if utxo_to_cancel is None:
        raise ValueError(
            f"Order UTxO {order_tx_hash}#{order_tx_index} not found in batching contract"
        )

    builder = TransactionBuilder(_blockfrost_context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": ["Cancel Order"]}})
        )
    )
    builder.add_input_address(user_address)
    # The batching validator checks that the order owner signed the transaction.
    # Include the owner's payment key hash as a required signer in the tx body.
    user_addr_obj = Address.from_primitive(user_address)
    if user_addr_obj.payment_part is not None:
        builder.required_signers = [user_addr_obj.payment_part]
    builder.add_script_input(
        utxo_to_cancel,
        batching_script,
        None,
        Redeemer(batching.CancelOrder()),
    )
    builder.ttl = _blockfrost_context.last_block_slot + 100

    try:
        tx_body = builder.build(change_address=user_address)
    except TransactionFailedException as exc:
        raise ValueError(
            "Unable to build cancel-order transaction. "
            "Ensure user_address owns the order and can sign the transaction."
        ) from exc
    transaction = Transaction(
        transaction_body=tx_body,
        transaction_witness_set=builder.build_witness_set(),
        auxiliary_data=builder.auxiliary_data,
    )

    return transaction.to_cbor_hex()


async def mint_farm_token(
    user_address: Address,
    farm_token_str: str,
    amount: int,
):
    farm_token = token_from_string(farm_token_str)
    free_minting_contract_script, free_minting_contract_hash, _ = get_contract(
        "free_mint", compressed=True
    )

    if farm_token.policy_id != free_minting_contract_hash.payload:
        raise ValueError("Requested farm token is not mintable by the free_mint policy")

    # Use Blockfrost for all chain queries: UTxO fetch, protocol params, chain tip
    # are all fast REST calls instead of slow Ogmios WebSocket roundtrips.
    builder = TransactionBuilder(_blockfrost_context)
    builder.auxiliary_data = AuxiliaryData(
        data=AlonzoMetadata(
            metadata=Metadata({674: {"msg": [f"Mint farm token x{amount}"]}})
        )
    )
    builder.add_input_address(user_address)
    # free_mint validator is a no-op; supply known ex-units to skip script evaluation.
    builder.add_minting_script(
        free_minting_contract_script,
        Redeemer(0, ex_units=ExecutionUnits(mem=3_000, steps=600_000)),
    )

    mint = MultiAsset(
        {
            free_minting_contract_hash: Asset(
                {AssetName(farm_token.token_name): amount}
            )
        }
    )

    builder.add_output(
        TransactionOutput(
            address=user_address,
            amount=Value(coin=2_000_000, multi_asset=mint),
        )
    )
    builder.mint = mint
    builder.ttl = _blockfrost_context.last_block_slot + 100

    tx_body = builder.build(change_address=user_address)
    transaction = Transaction(
        transaction_body=tx_body,
        transaction_witness_set=builder.build_witness_set(),
        auxiliary_data=builder.auxiliary_data,
    )

    return transaction.to_cbor_hex()
