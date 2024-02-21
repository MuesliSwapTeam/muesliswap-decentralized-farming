MuesliSwap On-Chain Staking
---------------------------

This repository contains the documentation and code for the implementation of MuesliSwap On-Chain Staking.

### Structure

- `onchain`: Contains the code for the on-chain part of the staking system i.e. Smart Contracts written in OpShin
- `offchain`: Contains the code for the off-chain part of the staking system i.e. building and submitting transactions for interaction with the Smart Contracts
- `api`: Contains code for the REST API that provides information about the staking system
    - `chain_querier`: Contains the code for querying the blockchain for information about the staking system and tracking the current state of the system in a database
    - `db_querier`: Contains the code for querying data from the database to prepare it for the REST API
    - `server`: Contains the code for the server that supplies information about the staking system via a REST API
