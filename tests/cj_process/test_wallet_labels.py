import unittest

from cj_process.parse_cj_logs import count_wallet_records


class WalletLabelsTest(unittest.TestCase):
    def test_count_wallet_records_ignores_unattributed_records(self):
        records = {
            "0": {"wallet_name": "wallet-000"},
            "1": {"address": "unattributed-output"},
            "2": {"wallet_name": "wallet-001"},
        }

        self.assertEqual(count_wallet_records(records, "wallet-000"), 1)
        self.assertEqual(count_wallet_records(records, "wallet-001"), 1)
        self.assertEqual(count_wallet_records(records, "wallet-002"), 0)


if __name__ == "__main__":
    unittest.main()
