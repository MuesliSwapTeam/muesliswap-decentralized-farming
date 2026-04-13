from pathlib import Path

import click
from pycardano import Address, Network, PaymentSigningKey, PaymentVerificationKey

keys_dir = Path(__file__).parent.parent.joinpath("keys")


@click.command()
@click.argument("name")
def main(name):
    """
    Creates a testnet signing key, verification key, and address.
    """
    keys_dir.mkdir(exist_ok=True)
    skey_path = keys_dir.joinpath(f"{name}.skey")
    vkey_path = keys_dir.joinpath(f"{name}.vkey")
    addr_path = keys_dir.joinpath(f"{name}.addr")
    testnet_addr_path = keys_dir.joinpath(f"{name}.test_addr")

    if skey_path.exists():
        raise FileExistsError(
            f"Signing key file already exists: {skey_path}. "
            f"Choose a different name or remove the existing file first."
        )
    if vkey_path.exists():
        raise FileExistsError(
            f"Verification key file already exists: {vkey_path}. "
            f"Choose a different name or remove the existing file first."
        )
    if addr_path.exists():
        raise FileExistsError(
            f"Mainnet address file already exists: {addr_path}. "
            f"Choose a different name or remove the existing file first."
        )
    if testnet_addr_path.exists():
        raise FileExistsError(
            f"Testnet address file already exists: {testnet_addr_path}. "
            f"Choose a different name or remove the existing file first."
        )

    signing_key = PaymentSigningKey.generate()
    signing_key.save(str(skey_path))

    verification_key = PaymentVerificationKey.from_signing_key(signing_key)
    verification_key.save(str(vkey_path))

    address = Address(payment_part=verification_key.hash(), network=Network.MAINNET)
    with open(addr_path, mode="w") as f:
        f.write(str(address))

    testnet_address = Address(
        payment_part=verification_key.hash(), network=Network.TESTNET
    )
    with open(testnet_addr_path, mode="w") as f:
        f.write(str(testnet_address))

    print(f"wrote signing key to: {skey_path}")
    print(f"wrote verification key to: {vkey_path}")
    print(f"wrote address to: {addr_path}")
    print(f"wrote testnet address to: {testnet_addr_path}")


if __name__ == "__main__":
    main()
