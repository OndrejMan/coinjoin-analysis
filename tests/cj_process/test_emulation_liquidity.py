"""Liquidity classification of emulated runs.

Emulation links coinjoins by address ('spend_by_txid') and exports every block, so
remixed outputs must become MIX_REMIX and outputs spent outside the mix MIX_LEAVE,
not MIX_STAY.
"""

from cj_process.emulation_postmix import build_emulation_postmix


CJ_A = "a" * 64
CJ_B = "b" * 64
POSTMIX = "c" * 64
FUNDING = "d" * 64


def emulated_coinjoins():
    return {
        CJ_A: {
            "txid": CJ_A,
            "broadcast_time": "2026-10-05 12:00:00.000",
            "inputs": {"0": {"address": "fresh-a", "value": 300000, "txid": FUNDING}},
            "outputs": {
                "0": {"address": "remixed", "value": 100000},
                "1": {"address": "left", "value": 100000},
                "2": {"address": "stayed", "value": 99000},
            },
        },
        CJ_B: {
            "txid": CJ_B,
            "broadcast_time": "2026-10-05 12:10:00.000",
            "inputs": {
                "0": {"address": "remixed", "value": 100000, "txid": CJ_A},
                "1": {"address": "fresh-b", "value": 100000, "txid": FUNDING},
            },
            "outputs": {
                "0": {"address": "b-out-0", "value": 99500},
                "1": {"address": "b-out-1", "value": 99500},
            },
        },
    }


def raw_block_txs():
    def vout(n, btc, address):
        return {"n": n, "value": btc, "scriptPubKey": {"address": address}}

    return {
        CJ_A: {
            "txid": CJ_A,
            "mine_time": "2026-10-05 12:00:00.000",
            "vin": [{"txid": FUNDING, "vout": 0}],
            "vout": [vout(0, 0.001, "remixed"), vout(1, 0.001, "left"), vout(2, 0.00099, "stayed")],
        },
        CJ_B: {
            "txid": CJ_B,
            "mine_time": "2026-10-05 12:10:00.000",
            "vin": [{"txid": CJ_A, "vout": 0}, {"txid": FUNDING, "vout": 1}],
            "vout": [vout(0, 0.000995, "b-out-0"), vout(1, 0.000995, "b-out-1")],
        },
        POSTMIX: {
            "txid": POSTMIX,
            "mine_time": "2026-10-05 12:30:00.000",
            "vin": [{"txid": CJ_A, "vout": 1}],
            "vout": [vout(0, 0.00099, "external")],
        },
        FUNDING: {
            "txid": FUNDING,
            "mine_time": "2026-10-05 11:00:00.000",
            "vin": [{"coinbase": "00"}],
            "vout": [vout(0, 0.003, "fresh-a"), vout(1, 0.001, "fresh-b")],
        },
    }


def test_postmix_contains_only_spends_of_coinjoin_outputs():
    postmix = build_emulation_postmix(emulated_coinjoins(), raw_block_txs())

    assert list(postmix) == [POSTMIX]
    assert postmix[POSTMIX]["broadcast_time"] == "2026-10-05 12:30:00.000"
    assert postmix[POSTMIX]["inputs"]["0"] == {
        "spending_tx": f"vout_{CJ_A}_1",
        "value": 100000,
        "address": "left",
    }
    assert postmix[POSTMIX]["outputs"]["0"] == {"value": 99000, "address": "external"}

