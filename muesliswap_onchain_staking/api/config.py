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

# default: start from a block around 19 feb 2024
START_BLOCK_SLOT = 	68_140_290 if network == Network.TESTNET else 125_125_931
START_BLOCK_HASH = (
    "9e4623ff2713164b7d950cff69b596f9cd4e8b95de28b6bc6e28d64ee2db7872"
    if network == Network.TESTNET
    else "bde676ad40372bde8cd778c035ac606976c07ec7dde261f313f3ea39cc196c74"
)