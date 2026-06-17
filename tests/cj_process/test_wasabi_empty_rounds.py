import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cj_process import parse_cj_logs


class WasabiEmptyRoundsTest(unittest.TestCase):
    def test_process_experiment_allows_wasabi_logs_without_complete_rounds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            log_path = run_dir / "data" / "wasabi-coordinator" / "coordinator" / "Logs.txt"
            log_path.parent.mkdir(parents=True)
            log_path.write_text("round started but not completed\n", encoding="utf-8")

            option_overrides = {
                "LOAD_TXINFO_FROM_FILE": False,
                "LOAD_TXINFO_FROM_DOCKER_FILES": True,
                "READ_ONLY_COINJOIN_TX_INFO": False,
                "ASSUME_COORDINATOR_WALLET": False,
                "PARSE_ERRORS": True,
                "LOAD_COMPUTED_TRANSACTION_INFO": False,
                "SAVE_ANALYTICS_TO_FILE": False,
                "GENERATE_COINJOIN_GRAPH_BLIND": False,
                "GENERATE_COINJOIN_GRAPH": False,
            }
            options = parse_cj_logs.EmulParseOptions()
            for name, value in option_overrides.items():
                setattr(options, name, value)

            with (
                mock.patch.object(parse_cj_logs, "op", options, create=True),
                mock.patch.object(parse_cj_logs, "load_tx_database_from_btccore", return_value={}),
                mock.patch.object(parse_cj_logs, "obtain_wallets_info", return_value=({}, {})),
                mock.patch.object(parse_cj_logs, "find_wasabi_coordinator_log_files", return_value=[str(log_path)]),
                mock.patch.object(parse_cj_logs, "parse_backend_coinjoin_logs", return_value={}),
                mock.patch.object(parse_cj_logs, "load_prison_data"),
                mock.patch.object(parse_cj_logs, "load_anonscore_data"),
                mock.patch.object(parse_cj_logs.als, "remove_link_between_inputs_and_outputs"),
                mock.patch.object(parse_cj_logs.als, "compute_link_between_inputs_and_outputs"),
                mock.patch.object(parse_cj_logs.als, "analyze_input_out_liquidity"),
            ):
                result = parse_cj_logs.process_experiment((str(run_dir), False))

            self.assertEqual(result["coinjoins"], {})
            self.assertEqual(result["rounds"], {"no_round": []})

            coinjoin_info = json.loads((run_dir / "coinjoin_tx_info.json").read_text(encoding="utf-8"))
            coinjoin_stats = json.loads((run_dir / "coinjoin_tx_info_stats.json").read_text(encoding="utf-8"))
            self.assertEqual(coinjoin_info["coinjoins"], {})
            self.assertEqual(coinjoin_info["rounds"], {"no_round": []})
            self.assertEqual(coinjoin_stats["num_coinjoins"], 0)


if __name__ == "__main__":
    unittest.main()
