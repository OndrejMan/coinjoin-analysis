#!/usr/bin/env bash

# Prepare expected environment
BASE_PATH=$HOME
source $BASE_PATH/btc/coinjoin-analysis/scripts/activate_env.sh

#
# Prepare perf measurement
# 
set -euo pipefail
# Start log_perf.sh (background)
setsid $BASE_PATH/btc/coinjoin-analysis/scripts/log_perf.sh &
PERF_PID=$!
echo "=== $(date -Is) log_perf.sh is starting ==="
# Always stop log_perf.sh if we exit for any reason
cleanup() {
  echo "=== $(date -Is) stopping log_perf.sh (pid=$PERF_PID) ==="
  kill "$PERF_PID" 2>/dev/null || true
  wait "$PERF_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Run debug processing
#$BASE_PATH/btc/coinjoin-analysis/scripts/temp_daily.sh


# Run standard daily processing
$BASE_PATH/btc/coinjoin-analysis/scripts/process_daily.sh



