import subprocess
import sys
from pathlib import Path
from typing import Union
from uplc.ast import PlutusByteString, plutus_cbor_dumps

from muesliswap_onchain_staking.onchain import (
    batching,
    staking,
    free_mint,
    farm_nft,
    unstake_permission_nft,
)
from muesliswap_onchain_staking.utils.to_script_context import to_address
from muesliswap_onchain_staking.utils.contracts import get_contract, module_name


def build_compressed(
    type: str, script: Union[Path, str], cli_options=("--cf",), args=()
):
    script = Path(script)
    command = [
        sys.executable,
        "-m",
        "opshin",
        *cli_options,
        "build",
        type,
        script,
        *args,
        "--recursion-limit",
        "3000",
    ]
    subprocess.run(command)

    built_contract = Path(f"build/{script.stem}/script.cbor")
    built_contract_compressed_cbor = Path(f"build/tmp.cbor")

    with built_contract_compressed_cbor.open("wb") as fp:
        subprocess.run(["plutonomy-cli", built_contract, "--default"], stdout=fp)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "uplc",
            "build",
            "--from-cbor",
            built_contract_compressed_cbor,
            "-o",
            f"build/{script.stem}_compressed",
            "--recursion-limit",
            "2000",
        ]
    )


def main():
    build_compressed(
        "minting",
        farm_nft.__file__,
        args=[plutus_cbor_dumps(PlutusByteString(b"farm")).hex()],
    )
    _, farm_nft_script_hash, _ = get_contract(
        module_name(farm_nft), compressed=True
    )

    build_compressed(
        "minting",
        unstake_permission_nft.__file__,
    )
    _, unstake_permission_nft_script_hash, _ = get_contract(
        module_name(unstake_permission_nft), compressed=True
    )

    build_compressed(
        "spending",
        staking.__file__,
        args=[
            plutus_cbor_dumps(
                PlutusByteString(farm_nft_script_hash.payload)
            ).hex(),
            plutus_cbor_dumps(
                PlutusByteString(unstake_permission_nft_script_hash.payload)
            ).hex(),
        ],
        cli_options=("--cf", "--allow-isinstance-anything"),
    )
    _, _, staking_address = get_contract(module_name(staking), compressed=True)

    build_compressed(
        "spending",
        batching.__file__,
        args=[
            to_address(staking_address).to_cbor().hex(),
        ],
    )

    build_compressed("rewarding", free_mint.__file__)


if __name__ == "__main__":
    main()
