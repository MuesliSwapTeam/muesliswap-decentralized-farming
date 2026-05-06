# MuesliSwap Decentralized Farming

This repository contains the documentation and code for the implementation of the MuesliSwap Decentralized Farming project funded in Fund 12 by Project Catalyst [1]. Progress will be published here regularly throughout the project.


## User Guide

This project provides an API and helper scripts for decentralized farming actions like creating farms and placing stake orders.

Main codebase parts:

- `muesliswap_onchain_staking/api`: API endpoints and server startup.
- `muesliswap_onchain_staking/offchain`: User-facing scripts that build and submit transactions.
- `muesliswap_onchain_staking/onchain`: Smart contract logic that validates farming and staking rules.

Typical user flow:

1. Install dependencies and start the API server.
2. Create a local key pair for test interactions.
3. Create a farm (pool configuration and reward settings).
4. Place a stake order into the selected farm.
5. Repeat actions as needed to test or operate the farming flow.

Use the commands in the next section for each step.

## Quickstart Commands

Install dependencies:

```bash
poetry install
```

Run the API server:

```bash
poetry run uvicorn muesliswap_onchain_staking.api.server:app --host 0.0.0.0 --port 8001 --reload
```

Create a local key pair:

```bash
poetry run python -m muesliswap_onchain_staking.create_key_pair demo_wallet
```

Create a farm:

```bash
poetry run python -m muesliswap_onchain_staking.offchain.create_farm
```

Place a stake order:

```bash
poetry run python -m muesliswap_onchain_staking.offchain.place_stake_order
```

## Developer Setup Guide

Use this setup for local development and testing.

1. Install Python and Poetry.
2. Run `poetry install` to install all project dependencies.
3. Start the API server with reload mode for fast development.
4. Use the provided offchain scripts to test farm creation and staking flows.
5. Keep changes small and run the same commands after updates to verify behavior.

## Structure and Ideas behind SCs

- `muesliswap_onchain_staking/onchain`: Contains the code for the on-chain part of the staking system, i.e., the following set of smart contracts written in OpShin:
    - `staking`: Each UTxO locked here represents either:
        - A staking position (in one of the pools) and contains the staked tokens. The datum maintains information such as the owner's address, the pool's ID, and a timestamp of the position's creation.
        - A staking pool / farm, i.e., has parameters such as stake token, reward token, emission rate, amount staked, etc. in its datum, and contains an NFT minted from `farm_nft` with its unique pool ID as a token name. Importantly, the `farm` datum also contains the so-called `cumulative_rewards_per_token` value which represents the total amount of tokens rewarded to stakers per staked token since the pool's creation. On each pool interaction (i.e. creation of a new staking position, unstaking, emission rate update, etc.), the respective `farm` needs to be spent and the `cumulative_rewards_per_token` value updated accordingly using the current timestamp, the last updated time, and the current amount of staked tokens. This enables reward computation via a "difference of partial sums" type of approach: By aditionally storing the value of `cumulative_rewards_per_token` at creation of each staking position in that position's datum we can calculate the amount of rewards to be distributed to the staker upon unstaking (despite the fact that per-token emission rates change due to other stakers coming and going).


## References

[1]: [Decentralized Farming Contracts](https://projectcatalyst.io/funds/12/f12-cardano-open-developers/decentralized-farming-contracts)
