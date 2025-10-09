#!/usr/bin/env python3
"""
Scan subfolders like results_YYYYMMDD under path X, read Scanner/Y.json in each,
extract metrics, and plot two stacked (top/bottom) 16:9-style graphs sorted by date.
Saves a single PNG in X.

Usage:
    python scan_results_plot.py /path/to/X Y

This will look for:
    /path/to/X/results_YYYYMMDD/Scanner/Y.json
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, Any, List, Tuple

import numpy as np
import matplotlib.pyplot as plt

RESULTS_DIR_PATTERN = re.compile(r"^results_(\d{8})$")  # captures YYYYMMDD

# All keys we need from JSONs
REQUIRED_KEYS = [
    "total_coinjoins",
    "total_fresh_inputs_value",
    "total_fresh_inputs_without_nonstandard_outputs_value",
    "min_inputs",
    "median_inputs",
    "max_inputs",
]

# Grouping for plots
TOP_SERIES = [
    "total_coinjoins",
    "total_fresh_inputs_value",
    "total_fresh_inputs_without_nonstandard_outputs_value",
]
BOTTOM_SERIES = [
    "min_inputs",
    "median_inputs",
    "max_inputs",
]


def find_result_dirs(base_path: str) -> List[Tuple[str, str]]:
    """Return list of (dirpath, yyyymmdd) for direct subfolders matching results_YYYYMMDD."""
    try:
        entries = os.listdir(base_path)
    except FileNotFoundError:
        print(f"ERROR: Base path not found: {base_path}", file=sys.stderr)
        sys.exit(1)

    matches: List[Tuple[str, str]] = []
    for name in entries:
        full = os.path.join(base_path, name)
        if not os.path.isdir(full):
            continue
        m = RESULTS_DIR_PATTERN.match(name)
        if m:
            matches.append((full, m.group(1)))
    return matches


def read_metrics(json_path: str) -> Dict[str, Any]:
    """Read JSON and return required metrics; raise if missing."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    metrics = {}
    for key in REQUIRED_KEYS:
        if key not in data:
            raise KeyError(f"  Missing key '{key}'")
        metrics[key] = data[key]
    return metrics


def parse_dates(keys: List[str]) -> List[datetime]:
    """Parse YYYYMMDD strings to datetime (for matplotlib)."""
    return [datetime.strptime(k, "%Y%m%d") for k in keys]


def main():
    parser = argparse.ArgumentParser(description="Scan results_* folders and plot metrics.")
    parser.add_argument("path_x", help="Base path X containing results_YYYYMMDD subfolders")
    parser.add_argument("filename_y", help="Filename Y (without .json) inside Scanner folder")
    args = parser.parse_args()

    base = os.path.abspath(args.path_x)
    yname = args.filename_y

    if not os.path.isdir(base):
        print(f"ERROR: '{base}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    result_dirs = find_result_dirs(base)
    if not result_dirs:
        print(f"ERROR: No subfolders like 'results_YYYYMMDD' found under {base}", file=sys.stderr)
        sys.exit(1)

    collected: Dict[str, Dict[str, Any]] = {}
    skipped = 0

    for folder_path, yyyymmdd in result_dirs:
        json_path = os.path.join(folder_path, "Scanner", f"{yname}.json")
        if not os.path.isfile(json_path):
            skipped += 1
            continue
        try:
            metrics = read_metrics(json_path)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            print(f"WARNING: Skipping {json_path}: {e}", file=sys.stderr)
            skipped += 1
            continue
        collected[yyyymmdd] = metrics

    if not collected:
        print("ERROR: No valid JSON files found with the required keys.", file=sys.stderr)
        sys.exit(1)

    # Sort by date
    date_keys_sorted = sorted(collected.keys())
    dates = parse_dates(date_keys_sorted)

    # Build series dict
    series: Dict[str, List[float]] = {k: [] for k in REQUIRED_KEYS}
    for dkey in date_keys_sorted:
        m = collected.get(dkey, {})
        for k in REQUIRED_KEYS:
            series[k].append(m.get(k, np.nan))

    # Two rows (stacked), each ~16:9 width:height panel
    # Overall figure ~16x18 inches so each axes ~16x9 with minimal padding.
    fig, (ax_top, ax_bottom) = plt.subplots(
        2, 1, figsize=(16, 9), sharex=True, constrained_layout=True
    )

    # Top plot
    for k in TOP_SERIES:
        ax_top.plot(dates, series[k], marker="o", linewidth=1.8, label=k, alpha=0.7)
    ax_top.set_title("Coinjoins & Fresh Inputs")
    ax_top.set_ylabel("Value")
    ax_top.grid(True, alpha=0.3, linestyle="--")
    ax_top.legend(loc="best", frameon=False)

    # Bottom plot
    for k in BOTTOM_SERIES:
        ax_bottom.plot(dates, series[k], marker="o", linewidth=1.8, label=k)
    ax_bottom.set_title("Inputs - min / median / max")
    ax_bottom.set_xlabel("Date")
    ax_bottom.set_ylabel("Count")
    ax_bottom.grid(True, alpha=0.3, linestyle="--")
    ax_bottom.legend(loc="best", frameon=False)

    for label in ax_bottom.get_xticklabels():
        label.set_rotation(45)
        label.set_horizontalalignment("right")

    fig.suptitle(f"Metrics from results_* for '{yname}.json'")
    # constrained_layout handles spacing; no tight_layout call needed.

    out_png = os.path.join(base, f"{yname}_metrics_stacked.png")
    plt.savefig(out_png, dpi=150)
    print(f"Done. Saved: {out_png}")
    if skipped:
        print(f"  Note: Skipped {skipped} folders due to missing/invalid JSON.", file=sys.stderr)


if __name__ == "__main__":
    main()
