# CoinJoin Analysis: architecture and data flow

This document is a source-grounded orientation guide for the `coinjoin-analysis`
repository. It describes what the project owns, which data it consumes, how the
mainnet and emulation paths differ, and which files are inputs versus generated
outputs.

Verified against the local `main` branch on 2026-07-16.

## Project responsibility

`coinjoin-analysis` is a Python research toolkit for processing, analyzing, and
visualizing CoinJoin transactions. It is not the component that creates CoinJoin
transactions and, in the mainnet workflow, it is not the component that scans
Bitcoin Core for candidate transactions.

Its main responsibilities are:

1. parse protocol-specific source data;
2. normalize it into the common `coinjoin_tx_info.json` structure;
3. connect transaction inputs and outputs to known wallets where labels exist;
4. calculate CoinJoin, wallet, liquidity, remix, and anonymity statistics;
5. write machine-readable JSON results and PNG/PDF visualizations.

The two supported data paths are not two analysis quality levels. They are two
different sources of evidence with different assumptions.

## High-level data flow

```text
Mainnet:
Bitcoin Core -> Dumplings heuristics -> Dumplings files
             -> parse_dumplings.py -> coinjoin_tx_info.json
             -> false-positive filtering -> statistics and plots

Emulation:
coinjoin-emulator -> exported blocks + wallet artifacts + protocol labels/logs
                  -> parse_cj_logs.py --action collect_docker
                  -> coinjoin_tx_info.json -> statistics and plots
```

Both paths eventually use a common CoinJoin transaction representation, but
their labels have different meaning:

- mainnet labels are heuristic detections and do not provide a known mapping of
  coins and addresses to real users;
- emulator labels come from a controlled experiment, where the participating
  clients and their addresses are known. This provides experimental ground
  truth, although regtest behavior is not automatically representative of the
  public Bitcoin network.

## Mainnet path

Entry point:

```bash
PYTHONPATH=src python src/cj_process/parse_dumplings.py \
  --cjtype ww2 \
  --action process_dumplings \
  --target-path <dumplings-output>
```

The analyzer consumes files previously produced by the external Dumplings
project. Dumplings performs the sequential Bitcoin mainnet scan and applies
protocol-oriented detection heuristics. `coinjoin-analysis` does not replace
that initial detector.

The mainnet workflow then:

1. converts Dumplings records into `coinjoin_tx_info.json` and related files;
2. performs additional, iterative false-positive detection;
3. keeps manually confirmed false positives in `false_cjtxs.json` rather than
   rewriting the large base dataset;
4. calculates remix, liquidity, input-distribution, and time-series results;
5. generates JSON, PNG, and PDF artifacts.

Main limitation: a transaction that looks like a CoinJoin is not necessarily a
real CoinJoin. Both false positives and false negatives are possible, and
wallet ownership is generally unknown.

## Emulation path

Entry point:

```bash
PYTHONPATH=src python src/cj_process/parse_cj_logs.py \
  --action collect_docker \
  --target-path <directory-containing-experiment-directories>
```

`--target-path` points to a parent directory. Each immediate child containing a
`data/` directory is treated as one experiment. The parser reads static files;
it does not need live Wasabi, JoinMarket, or Bitcoin Core RPC for
`collect_docker`.

### Expected emulator artifact layout

```text
<experiment>/
├── scenario.json
└── data/
    ├── btc-node/
    │   ├── block_0.json
    │   ├── block_1.json
    │   └── ...
    ├── wasabi-client-000/ or jcs-000/
    │   ├── coins.json
    │   ├── unspent_coins.json
    │   ├── keys.json
    │   └── protocol logs, when captured
    ├── additional client directories
    ├── wasabi-backend*/ or wasabi-coordinator*/
    │   └── Logs.txt
    ├── joinmarket_round_events.json
    └── coinjoin_label_manifest.json
```

Not every file is consumed directly by `parse_cj_logs.py`. The relevant input
contracts are described below.

### 1. Exported blockchain data

Consumed files:

```text
data/btc-node/block_*.json
```

`load_tx_database_from_btccore()` loads every transaction from the exported
verbose blocks into a `txid -> transaction` dictionary. The parser also adds a
`mine_time` derived from the block timestamp.

This database supplies the transaction facts:

- transaction IDs;
- inputs and referenced previous outputs;
- output values, scripts, and addresses;
- block and mining-time information.

Protocol logs or event labels identify a CoinJoin transaction ID. The complete
inputs and outputs are then reconstructed from this exported block database by
`extract_tx_info()`.

### 2. Wallet ownership data

Consumed for every `data/wasabi-client-*` or `data/jcs-*` directory:

```text
coins.json
keys.json
```

`obtain_wallets_info()` normalizes the directory name to `wallet-*`, loads its
known addresses and coins, and creates the data used to map an address to the
emulated wallet that controls it.

For Wasabi coins, missing `anonymityScore` is currently defaulted to `1`.
JoinMarket clients may return a protocol-specific unavailable marker instead of
wallet RPC-style data; the parser tolerates that case but has less wallet-level
information.

`unspent_coins.json` is produced by `coinjoin-emulator`, but the current
`collect_docker` implementation does not read it directly.

### 3. Positive CoinJoin labels

The exported blocks show what transactions exist, but do not by themselves say
which transactions were intentionally created as CoinJoins. The analyzer uses
protocol-specific producer evidence for that label.

#### Wasabi

The analyzer searches known and wildcarded coordinator/backend locations for
`Logs.txt`, including `data/wasabi-backend*` and
`data/wasabi-coordinator*` layouts.

`parse_backend_coinjoin_logs()` extracts:

- created round identifiers and timestamps;
- successfully broadcast CoinJoin transaction IDs;
- blame-round relationships;
- selected error states.

If present, `Prison.txt` is also loaded for Wasabi prison statistics.

#### JoinMarket

Source precedence is implemented in `process_experiment()`:

1. if `data/jcs-000/joinmarket` exists, parse `jmwalletd.log` files from all
   captured JoinMarket client directories;
2. otherwise, if present, parse `data/joinmarket_round_events.json` (or the
   compatibility location `<experiment>/joinmarket_round_events.json`);
3. otherwise continue to the Wasabi coordinator-log path.

The round-event fallback accepts a record as a CoinJoin only when:

- it has a transaction ID;
- the transaction can be reconstructed from the exported block database;
- an event timestamp or mining timestamp is available;
- a round ID does not conflict with a different transaction ID.

See `docs/joinmarket-round-events.md` for the detailed event contract.

`coinjoin_label_manifest.json` is producer provenance and completeness evidence.
The current direct `coinjoin-analysis` `collect_docker` path does not validate
the manifest itself; validation may be performed by the surrounding pipeline.

### Files present but not primary analyzer inputs

- `scenario.json` describes how the emulator run was configured, but the current
  `process_experiment()` path does not use it to reconstruct CoinJoins.
- `unspent_coins.json` is stored as experiment evidence but is not directly read
  by `obtain_wallets_info()`.
- `emulation_logs.zip` is the archive form of the experiment. Its contents must
  be available in the directory layout expected by the analyzer.

## Emulation outputs

These files are generated by `coinjoin-analysis`; they are not original emulator
inputs:

- `coinjoin_tx_info.json`: normalized CoinJoin transactions, rounds, wallet
  information, and address-to-wallet mapping;
- `coinjoin_tx_info_stats.json`: derived per-run and per-wallet statistics;
- `wallets_info.json`: normalized addresses grouped by wallet;
- `wallets_coins.json`: normalized coins grouped by wallet;
- `serialized_annonymity.json`: serialized wallet-coin anonymity data (the
  misspelling is part of the existing file contract);
- `coinjoin_stats.3.png` and `coinjoin_stats.3.pdf`: summary visualizations;
- additional JSON statistics and aggregated visualizations for a batch of runs.

`--action analyze_only` starts from an already generated
`coinjoin_tx_info.json`. It does not repeat extraction from blocks, wallet files,
or protocol logs.

## Core emulation call path

```text
main()
  -> process_multiple_experiments()
    -> process_experiment()
      -> load_tx_database_from_btccore()
      -> obtain_wallets_info()
      -> one positive-label parser:
           joinmarket_parse_coinjoin_logs()
           joinmarket_parse_round_events()
           parse_backend_coinjoin_logs()
      -> build_address_wallet_mapping()
      -> load_prison_data()
      -> load_anonscore_data()
      -> compute_link_between_inputs_and_outputs()
      -> analyze_input_out_liquidity()
      -> analyze_coinjoin_stats()
      -> JSON and PNG/PDF outputs
```

## Important source map

- `src/cj_process/parse_cj_logs.py`: emulation CLI, input discovery, parsing,
  normalization, analysis orchestration, and output generation;
- `src/cj_process/parse_dumplings.py`: Dumplings/mainnet workflow;
- `src/cj_process/cj_analysis.py`: shared transaction, liquidity, and analysis
  helpers, including precise BTC-to-satoshi conversion;
- `src/cj_process/cj_structs.py`: shared structures and enums;
- `src/cj_process/cj_consts.py`: constants;
- `src/emulation/anonymity_score.py`: wallet-coin anonymity parsing used by the
  emulation workflow;
- `src/helpers/`: older RPC and live-wallet automation helpers; these are not the
  main input path for `collect_docker`;
- `tests/cj_process/`: parser, validation, empty-data, amount-conversion, and
  pipeline tests.

## Verified robustness changes in the local history

The local Git history attributes the following changes to Ondrej Man:

- Docker image, entrypoint, Compose service, and container-image CI workflow;
- Wasabi 2.6 artifact-layout support;
- exact BTC-to-satoshi conversion using `Decimal(str(value))` to avoid binary
  float truncation;
- portable paths instead of selected hard-coded paths;
- graceful handling of empty CoinJoin runs and empty aggregate/liquidity data;
- handling of unlabeled wallet records;
- JoinMarket `joinmarket_round_events.json` fallback;
- rejection of missing/undecodable transactions, missing timestamps, and round
  IDs that map to multiple transaction IDs;
- focused tests for these cases.

## Known caveats

- Mainnet results are heuristic and lack wallet ownership ground truth.
- Emulator results have experimental labels but may not represent mainnet user
  behavior or scale.
- JoinMarket wallet-level mappings can be incomplete when the client cannot
  export Wasabi-style coin/key data.
- The code contains historical `collect_local` RPC support and helper modules;
  these should not be confused with the current static-file `collect_docker`
  workflow.
- Some artifact names and comments retain historical spelling or terminology;
  changing them can break downstream consumers.

## Quick verification commands

```bash
# Find the emulation entry point and input parsers.
rg -n "def (process_experiment|load_tx_database_from_btccore|obtain_wallets_info|joinmarket_parse_coinjoin_logs|joinmarket_parse_round_events|parse_backend_coinjoin_logs)" \
  src/cj_process/parse_cj_logs.py

# Run the focused test suite after installing project dependencies and pytest.
PYTHONPATH=src python -m pytest tests/cj_process
```
