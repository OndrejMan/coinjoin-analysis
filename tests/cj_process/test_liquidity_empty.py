import json
import tempfile
import unittest
from pathlib import Path

from cj_process.cj_analysis import analyze_input_out_liquidity
from cj_process.cj_structs import MIX_PROTOCOL


class LiquidityEmptyTest(unittest.TestCase):
    def test_analyze_input_out_liquidity_allows_empty_coinjoins(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = analyze_input_out_liquidity(
                tmpdir,
                {},
                {},
                {},
                MIX_PROTOCOL.JOINMARKET,
            )

            self.assertEqual(result, {})
            with open(Path(tmpdir) / "tx_reordering_stats.json", "r") as file:
                self.assertEqual(json.load(file), {})


if __name__ == "__main__":
    unittest.main()
