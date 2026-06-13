import tempfile
import unittest

from cj_process.parse_cj_logs import analyze_aggregated_coinjoin_stats


class AggregateEmptyTest(unittest.TestCase):
    def test_analyze_aggregated_coinjoin_stats_skips_empty_experiments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            analyze_aggregated_coinjoin_stats(
                {
                    f"{tmpdir}/empty-joinmarket": {
                        "coinjoins": {},
                        "wallets_info": {},
                        "analysis": {"path": f"{tmpdir}/empty-joinmarket"},
                    }
                },
                tmpdir,
            )


if __name__ == "__main__":
    unittest.main()
