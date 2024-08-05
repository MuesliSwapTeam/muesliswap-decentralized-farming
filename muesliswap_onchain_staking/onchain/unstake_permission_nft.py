from opshin.prelude import *
from opshin.std.builtins import *
from muesliswap_onchain_staking.onchain.util import *
from muesliswap_onchain_staking.onchain.batching_types import *


def validator(redeemer: UnstakeOrder, context: ScriptContext) -> None:
    """
    Permission NFT

    The presence of this NFT in an unstake order indicates that a third party may unstake
    the referenced position if the owner matches.
    """
    purpose = get_minting_purpose(context)
    tx_info = context.tx_info

    own_mint = tx_info.mint[purpose.policy_id]
    if all([amount < 0 for amount in own_mint.values()]):
        # Burning NFTs is always allowed
        # but we need to make sure that all mints with this policy are burning
        pass
    else:
        token_name = unstake_permission_nft_token_name(redeemer)
        assert user_signed_tx(
            redeemer.owner, tx_info
        ), "Only the owner may mint this NFT"

        check_mint_exactly_one_with_name(tx_info.mint, purpose.policy_id, token_name)
