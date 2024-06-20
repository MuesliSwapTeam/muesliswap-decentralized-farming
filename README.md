# MuesliSwap On-Chain Staking

This repository contains the code for the implementation of MuesliSwap On-Chain Staking.

## Structure and Ideas behind SCs

- `onchain`: Contains the code for the on-chain part of the staking system, i.e., the following set of smart contracts written in OpShin:
    - `staking`: Each UTxO locked here represents one staking position (in one of the pools) and contains the staked tokens. The datum maintains information such as the owner's address, the pool's ID, and a timestamp of the position's creation.
    - `farm`: Each UTxO locked here represents one staking pool, i.e., has parameters such as stake token, reward token, emission rate, amount staked, etc. in its datum, and contains an NFT minted from `farm_nft` with its unique pool ID as a token name. Importantly, the `farm` datum also contains the so-called `cumulative_rewards_per_token` value which represents the total amount of tokens rewarded to stakers per staked token since the pool's creation. On each pool interaction (i.e. creation of a new staking position, unstaking, emission rate update, etc.), the respective `farm` needs to be spent and the `cumulative_rewards_per_token` value updated accordingly using the current timestamp, the last updated time, and the current amount of staked tokens. This enables reward computation via a "difference of partial sums" type of approach: By aditionally storing the value of `cumulative_rewards_per_token` at creation of each staking position in that position's datum we can calculate the amount of rewards to be distributed to the staker upon unstaking (despite the fact that per-token emission rates change due to other stakers coming and going).
- `offchain`: Contains the code for the off-chain part of the staking system i.e. building and submitting transactions for interaction with the Smart Contracts
