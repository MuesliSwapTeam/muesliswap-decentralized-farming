#!/usr/bin/env bash

POETRY_BIN=/home/cardano-preprod/.local/bin/poetry

set -u

cd "$(dirname "$0")"

# Install/update dependencies once before entering the loop.
$POETRY_BIN install

SLEEP_SECONDS="${BATCHER_LOOP_SLEEP_SECONDS:-30}"
CMD_TIMEOUT_SECONDS="${BATCHER_CMD_TIMEOUT_SECONDS:-180}"
WALLET="${BATCHER_WALLET:-staker}"

echo "Starting farming batcher loop (wallet=${WALLET}, sleep=${SLEEP_SECONDS}s, timeout=${CMD_TIMEOUT_SECONDS}s)"

run_batch_step() {
  local module="$1"
  local label="$2"

  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Running ${label}"
  if ! timeout "${CMD_TIMEOUT_SECONDS}" \
    $POETRY_BIN run python -m "${module}" --wallet "${WALLET}"; then
    # These scripts are intentionally best-effort: "nothing to batch" and other
    # transient chain conditions should not stop the batcher loop.
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] ${label} failed (continuing loop)"
  fi
}

while true; do
  run_batch_step "muesliswap_onchain_staking.offchain.batch_stake_orders" "batch_stake_orders"
  run_batch_step "muesliswap_onchain_staking.offchain.batch_unstake_orders" "batch_unstake_orders"
  sleep "${SLEEP_SECONDS}"
done
