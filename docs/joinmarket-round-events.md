# JoinMarket round-event input contract

`collect_docker` can consume emulator-produced JoinMarket round labels when
usable copied client logs are unavailable.

## Discovery and precedence

The parser looks for either of these files:

1. `<run>/data/joinmarket_round_events.json`
2. `<run>/joinmarket_round_events.json`

Usable `data/jcs-*/joinmarket/jmwalletd.log` files have higher precedence. If
they contain no CoinJoin records and a round-event file exists, the parser falls
back to the round-event file. Empty JoinMarket directories do not suppress the
fallback.

## Fields used by the parser

Each list entry may contain:

- `round_id`, used as the normalized string round id;
- `txid`, required for a CoinJoin transaction record;
- `broadcast_time`, `timestamp`, or `round_start_time`, accepted as a Unix
  timestamp or ISO-8601 string and serialized with millisecond precision;
- arbitrary producer metadata, retained under `joinmarket_round_event`.

The transaction and every referenced input transaction must be present in the
exported raw transaction database. The parser never queries a live Bitcoin node
to complete round-event data. The transaction's `mine_time` may supply a missing
event timestamp. Missing or incomplete exported transactions are dropped from
`coinjoins`; a decodable transaction with no event or mine timestamp causes
parsing to fail instead of inventing a time.

Unix timestamps and timezone-aware ISO-8601 strings are normalized to UTC.
Timezone-free ISO-8601 strings retain their supplied wall-clock time.

The parser does not use event `status` as a substitute for transaction
evidence. Any decodable event with a transaction id and time is accepted. The
emulator's final reconciliation promotes late mined matches to `confirmed` and
preserves their earlier lifecycle failure in history fields.

## Accepted-round contract

The parser adds `rounds[round_id]` only after it validates `txid`, decodes the
transaction, and obtains an event or mining timestamp. Events dropped for a
missing or undecodable transaction are absent from both `coinjoins` and
`rounds`, so the two structures describe the same accepted event set.
