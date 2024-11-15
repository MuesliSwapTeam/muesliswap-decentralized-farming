import os

import blockfrost
import pycardano
from pycardano import Network
from pycardano.backend.ogmios_v6 import OgmiosV6ChainContext

ogmios_host = os.getenv("OGMIOS_API_HOST", "localhost")
ogmios_port = os.getenv("OGMIOS_API_PORT", "1338")
ogmios_protocol = os.getenv("OGMIOS_API_PROTOCOL", "ws")
ogmios_url = f"{ogmios_protocol}://{ogmios_host}:{ogmios_port}"

kupo_host = os.getenv("KUPO_API_HOST", "localhost")
kupo_port = os.getenv("KUPO_API_PORT", "6667")
kupo_protocol = os.getenv("KUPO_API_PROTOCOL", "http")
kupo_url = (
    f"{kupo_protocol}://{kupo_host}:{kupo_port}" if kupo_host is not None else None
)

network = Network.TESTNET

blockfrost_project_id = os.getenv("BLOCKFROST_PROJECT_ID", None)
blockfrost_client = blockfrost.BlockFrostApi(
    blockfrost_project_id,
    base_url=(
        blockfrost.ApiUrls.mainnet.value
        if network == Network.MAINNET
        else blockfrost.ApiUrls.preprod.value
    ),
)


# Load chain context
try:
    context = OgmiosV6ChainContext(
        host=ogmios_host,
        port=int(ogmios_port),
        secure=ogmios_protocol == "wss",
        network=network,
    )
except Exception as e:
    print("No ogmios available")
    context = None


def show_tx(signed_tx: pycardano.Transaction):
    print(f"transaction id: {signed_tx.id}")
    print(f"Cardanoscan: https://preprod.cexplorer.io/tx/{signed_tx.id}")
