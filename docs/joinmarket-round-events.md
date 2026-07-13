# JoinMarket round-event input contract

`collect_docker` can consume emulator-produced JoinMarket round labels when the
copied `data/jcs-000/joinmarket` client-log tree is unavailable.

## Discovery and precedence

The parser looks for either of these files:

1. `<run>/data/joinmarket_round_events.json`
2. `<run>/joinmarket_round_events.json`

Client logs have higher precedence. If `<run>/data/jcs-000/joinmarket` exists,
the client-log parser is used even when a round-event file is also present.

## Fields used by the parser

Each list entry may contain:

- `round_id`, used as the normalized string round id;
- `txid`, required for a CoinJoin transaction record;
- `broadcast_time`, `timestamp`, or `round_start_time`;
- arbitrary producer metadata, retained under `joinmarket_round_event`.

If an event has a transaction id present in the exported raw transaction
database, the transaction's `mine_time` may supply the timestamp. A transaction
id that cannot be decoded is dropped from `coinjoins`. A decodable transaction
with no event or mine timestamp causes parsing to fail instead of inventing a
time.

The parser does not use event `status` as a substitute for transaction
evidence. Any decodable event with a transaction id and time is accepted. The
emulator's final reconciliation promotes late mined matches to `confirmed` and
preserves their earlier lifecycle failure in history fields.

## Accepted-round contract

The parser adds `rounds[round_id]` only after it validates `txid`, decodes the
transaction, and obtains an event or mining timestamp. Events dropped for a
missing or undecodable transaction are absent from both `coinjoins` and
`rounds`, so the two structures describe the same accepted event set.
