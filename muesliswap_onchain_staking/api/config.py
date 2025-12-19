from pycardano import Network

from ..utils.contracts import module_name
from ..utils import network, contracts

from ..onchain import unstake_permission_nft, farm_nft, staking

# Only these scripts need to be hardcoded
# And should also change seldomly
_, unstake_permission_nft_policy_id, _ = contracts.get_contract(
    module_name(unstake_permission_nft), compressed=True
)
_, farm_nft_policy_id, _ = contracts.get_contract(
    module_name(farm_nft), compressed=True
)
_, _, staking_address = contracts.get_contract(
    module_name(staking), compressed=True
)

# default: start from a block around 07 dec 2025
START_BLOCK_SLOT = 109_430_896 if network == Network.TESTNET else 125_125_931
START_BLOCK_HASH = (
    "4e049562702158a2738744fcf6c7584542d798fed1a6caa285ba72f974dbecb2"
    if network == Network.TESTNET
    else "bde676ad40372bde8cd778c035ac606976c07ec7dde261f313f3ea39cc196c74"
)