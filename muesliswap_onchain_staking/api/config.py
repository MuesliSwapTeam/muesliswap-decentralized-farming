from pycardano import Network

from ..utils.contracts import module_name
from ..utils import network, contracts

from ..onchain import unstake_permission_nft, farm_nft, staking_nft

# Only these scripts need to be hardcoded
# And should also change seldomly
_, unstake_permission_nft_policy_id, _ = contracts.get_contract(
    module_name(unstake_permission_nft), compressed=True
)
_, farm_nft_policy_id, _ = contracts.get_contract(
    module_name(farm_nft), compressed=True
)
_, staking_nft_policy_id, _ = contracts.get_contract(
    module_name(staking_nft), compressed=True
)

# default: start from a block around 19 feb 2024
START_BLOCK_SLOT = 64_349_833 if network == Network.TESTNET else 125_125_931
START_BLOCK_HASH = (
    "516da005986406f121d08aa4cef563bca9e6e368b5e856c424fe4a6afc511958"
    if network == Network.TESTNET
    else "bde676ad40372bde8cd778c035ac606976c07ec7dde261f313f3ea39cc196c74"
)