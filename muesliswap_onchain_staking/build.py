import subprocess
import sys
from pathlib import Path
from typing import Union

from muesliswap_onchain_staking.onchain import batching, staking, stake_state, free_mint
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
        "2000",
    ]
    subprocess.run(command)


#    built_contract = Path(f"build/{script.stem}/script.cbor")
#    built_contract_compressed_cbor = Path(f"build/tmp.cbor")
#
#    with built_contract_compressed_cbor.open("wb") as fp:
#        subprocess.run(["plutonomy-cli", built_contract, "--default"], stdout=fp)
#
#    subprocess.run(
#        [
#            sys.executable,
#            "-m",
#            "uplc",
#            "build",
#            "--from-cbor",
#            built_contract_compressed_cbor,
#            "-o",
#            f"build/{script.stem}_compressed",
#            "--recursion-limit",
#            "2000",
#        ]
#    )


def main():
    for script in [staking, batching]:
        build_compressed("spending", script.__file__)
    build_compressed("rewarding", free_mint.__file__)
    _, _, staking_address = get_contract(module_name(staking), compressed=False)
    build_compressed(
        "spending",
        stake_state.__file__,
        args=[to_address(staking_address).to_cbor().hex()],
    )


if __name__ == "__main__":
    main()
