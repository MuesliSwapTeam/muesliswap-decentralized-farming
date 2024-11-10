# MuesliSwap Decentralized Farming

This repository contains the documentation and code for the implementation of the MuesliSwap Decentralized Farming project funded in Fund 12 by Project Catalyst [1]. Progress will be published here regularly throughout the project.


## Structure and Ideas behind SCs

- `muesliswap_onchain_staking/onchain`: Contains the code for the on-chain part of the staking system, i.e., the following set of smart contracts written in OpShin:
    - `staking`: Each UTxO locked here represents either:
        - A staking position (in one of the pools) and contains the staked tokens. The datum maintains information such as the owner's address, the pool's ID, and a timestamp of the position's creation.
        - A staking pool / farm, i.e., has parameters such as stake token, reward token, emission rate, amount staked, etc. in its datum, and contains an NFT minted from `farm_nft` with its unique pool ID as a token name. Importantly, the `farm` datum also contains the so-called `cumulative_rewards_per_token` value which represents the total amount of tokens rewarded to stakers per staked token since the pool's creation. On each pool interaction (i.e. creation of a new staking position, unstaking, emission rate update, etc.), the respective `farm` needs to be spent and the `cumulative_rewards_per_token` value updated accordingly using the current timestamp, the last updated time, and the current amount of staked tokens. This enables reward computation via a "difference of partial sums" type of approach: By aditionally storing the value of `cumulative_rewards_per_token` at creation of each staking position in that position's datum we can calculate the amount of rewards to be distributed to the staker upon unstaking (despite the fact that per-token emission rates change due to other stakers coming and going).


## References

[1]: [Decentralized Farming Contracts](https://projectcatalyst.io/funds/12/f12-cardano-open-developers/decentralized-farming-contracts)
