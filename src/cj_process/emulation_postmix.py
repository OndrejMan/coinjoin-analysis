"""Postmix spends of emulated runs, taken from the blocks the emulation exported.

The records have the same shape as the 'postmix' section parse_dumplings.py builds for
mainnet data, so analyze_input_out_liquidity() treats emulated and mainnet runs alike.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from cj_process.cj_analysis import (
    btc_to_sats,
    extract_txid_from_inout_string,
    get_input_name_string,
    get_output_name_string,
)

# A record of coinjoin_tx_info.json: a coinjoin, one of its inputs or outputs, or a postmix transaction.
Record = dict[str, Any]


@dataclass(frozen=True)
class Outpoint:
    """Output ``index`` of transaction ``txid``."""

    txid: str
    index: int

    @classmethod
    def from_name(cls, name: str) -> 'Outpoint':
        """Parse the 'vout_<txid>_<index>' reference used in coinjoin_tx_info.json."""
        txid, index = extract_txid_from_inout_string(name)
        return cls(txid, int(index))

    @property
    def name(self) -> str:
        return get_output_name_string(self.txid, self.index)


@dataclass(frozen=True)
class ExportedTransaction:
    """A transaction of the block export, as load_tx_database_from_btccore() returns it."""

    txid: str
    mine_time: str
    spends: tuple[Outpoint | None, ...]  # per input; None for a coinbase input
    outputs: tuple[Record, ...]  # {'value': sats, 'address': ...} by output index

    @classmethod
    def from_export(cls, tx: Record) -> 'ExportedTransaction':
        return cls(
            txid=tx['txid'],
            mine_time=tx['mine_time'],
            spends=tuple(Outpoint(vin['txid'], vin['vout']) if 'txid' in vin else None for vin in tx['vin']),
            outputs=tuple(
                {'value': btc_to_sats(vout['value']), 'address': vout['scriptPubKey'].get('address')}
                for vout in tx['vout']
            ),
        )

    def spends_coinjoin_output(self, coinjoins: dict[str, Record]) -> bool:
        return any(spent is not None and spent.txid in coinjoins for spent in self.spends)


def _coinjoin_output(coinjoins: dict[str, Record], outpoint: Outpoint) -> Record | None:
    """The parsed coinjoin output at ``outpoint``, or None when it is not a coinjoin output."""
    if outpoint.txid not in coinjoins:
        return None
    return coinjoins[outpoint.txid]['outputs'].get(str(outpoint.index))


def _coinjoin_outputs(coinjoins: dict[str, Record]) -> Iterator[Record]:
    """Every output record of every coinjoin."""
    return (output for record in coinjoins.values() for output in record['outputs'].values())


def _spent_output(
    outpoint: Outpoint,
    transactions: dict[str, ExportedTransaction],
) -> Record:
    """Value and address of the output at ``outpoint``; empty when the export lacks it."""
    prev_tx = transactions.get(outpoint.txid)
    return prev_tx.outputs[outpoint.index].copy() if prev_tx is not None else {}


def _postmix_record(
    tx: ExportedTransaction,
    transactions: dict[str, ExportedTransaction],
) -> Record:
    """One postmix transaction: the output each input spends and what each output pays."""
    inputs = {
        str(index): {'spending_tx': spent.name, **_spent_output(spent, transactions)}
        for index, spent in enumerate(tx.spends)
        if spent is not None
    }
    outputs = {str(index): dict(output) for index, output in enumerate(tx.outputs)}
    return {'txid': tx.txid, 'broadcast_time': tx.mine_time, 'inputs': inputs, 'outputs': outputs}


def build_emulation_postmix(coinjoins: dict[str, Record], raw_txs_db: dict[str, Record]) -> dict[str, Record]:
    """
    Return non-CoinJoin transactions that spend CoinJoin outputs.

    :param coinjoins: CoinJoin transactions keyed by txid
    :param raw_txs_db: exported transactions keyed by txid, from load_tx_database_from_btccore()
    :return: postmix transactions keyed by txid
    """
    transactions = {txid: ExportedTransaction.from_export(tx) for txid, tx in raw_txs_db.items()}
    return {
        tx.txid: _postmix_record(tx, transactions)
        for tx in transactions.values()
        if tx.txid not in coinjoins and tx.spends_coinjoin_output(coinjoins)
    }


def _reference_remixes(coinjoins: dict[str, Record]) -> None:
    """Point each coinjoin output spent by another coinjoin to that coinjoin."""
    for output in _coinjoin_outputs(coinjoins):
        spend_by_txid = output.get('spend_by_txid')
        if spend_by_txid is not None:
            spending_txid, index = spend_by_txid
            output['spend_by_tx'] = get_input_name_string(spending_txid, index)


def _reference_postmix_spends(coinjoins: dict[str, Record], postmix: dict[str, Record]) -> None:
    """Point each coinjoin output spent outside the mix to its postmix transaction."""
    for postmix_txid, record in postmix.items():
        for index, postmix_input in record['inputs'].items():
            coinjoin_output = _coinjoin_output(coinjoins, Outpoint.from_name(postmix_input['spending_tx']))
            if coinjoin_output is not None:
                coinjoin_output['spend_by_tx'] = get_input_name_string(postmix_txid, index)


def assign_emulation_spend_references(coinjoins: dict[str, Record], postmix: dict[str, Record]) -> None:
    """Fill in 'spend_by_tx' for emulated coinjoin outputs so analyze_input_out_liquidity() can classify them."""
    _reference_remixes(coinjoins)
    _reference_postmix_spends(coinjoins, postmix)
