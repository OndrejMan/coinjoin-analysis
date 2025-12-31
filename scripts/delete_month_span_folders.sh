#!/usr/bin/env bash
# delete_month_span_folders.sh
# GNU date required. On macOS: brew install coreutils and run with DATE_BIN=gdate
# Usage: ./delete_month_span_folders.sh 2024-12 "_unknown-static-100-1utxo" /path/to/base [--dry-run]

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 START_YYYY-MM FOLDER_SUFFIX BASE_PATH [--dry-run]"
  exit 1
fi

START_MM="$1"                 # e.g., 2024-12
SUFFIX="$2"                   # e.g., _unknown-static-100-1utxo
BASE_PATH="$3"                # e.g., /data/folders
DRY_RUN="${4-}"               # optional --dry-run
DATE_BIN="${DATE_BIN:-date}"  # set DATE_BIN=gdate on macOS

# Validate start month
if ! [[ "$START_MM" =~ ^[0-9]{4}-[0-9]{2}$ ]]; then
  echo "Error: START_YYYY-MM must look like 2024-12" >&2
  exit 2
fi

# Normalize base path and sanity-check
BASE_PATH="${BASE_PATH%/}"
if [[ -z "$BASE_PATH" || "$BASE_PATH" == "/" ]]; then
  echo "Refusing to operate on an empty base path or '/'. Pick a real directory." >&2
  exit 3
fi
if [[ ! -d "$BASE_PATH" ]]; then
  echo "Base path does not exist: $BASE_PATH" >&2
  exit 4
fi

# Month boundaries as ISO dates (no epoch arithmetic after @...!)
cur_month_iso="${START_MM}-01"
today_month_iso="$("$DATE_BIN" +%Y-%m-01)"

# Convert to epochs only for loop comparison
cur_epoch="$("$DATE_BIN" -d "$cur_month_iso" +%s)"
end_epoch="$("$DATE_BIN" -d "$today_month_iso" +%s)"

while [[ "$cur_epoch" -le "$end_epoch" ]]; do
  next_month_iso="$("$DATE_BIN" -d "$cur_month_iso +1 month" +%Y-%m-01)"

  folder="${cur_month_iso} 00-00-00--${next_month_iso} 00-00-00${SUFFIX}"
  fullpath="${BASE_PATH}/${folder}"

  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo "[DRY RUN] would delete: $fullpath"
  else
    if [[ -d "$fullpath" ]]; then
      echo "Deleting: $fullpath"
      rm -rf -- "$fullpath"
    else
      echo "Skip (not found): $fullpath"
    fi
  fi

  # advance one month (use ISO arithmetic, then update epoch)
  cur_month_iso="$next_month_iso"
  cur_epoch="$("$DATE_BIN" -d "$cur_month_iso" +%s)"
done
