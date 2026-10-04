"""Regression tests for data errors that could silently distort the dashboard."""

import csv
import json
import runpy
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = runpy.run_path(str(ROOT / "src/data_processing/validate_portfolio.py"))
VALIDATE = MODULE["validate_portfolio"]
CONTRACT_PATH = ROOT / "config/portfolio_contract.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


class PortfolioValidationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "portfolio.csv"
        self.row = {
            "ClientId": "SYNTHETIC-CLIENT-1", "policy_id": "SYNTHETIC-POLICY-1",
            "client_name": "Synthetic client", "state": "Synthetic state",
            "municipality": "Synthetic municipality", "coverage_type": "Test coverage",
            "industry": "Agricultura", "premium": "0.10", "sum_insured": "100.00",
            "policy_start_date": "2024-01-01", "policy_end_date": "2025-01-01",
            "fill_method": "original", "confidence_level": "high",
        }

    def check_rows(self, rows, fields=None, verify_snapshot=False):
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields or CONTRACT["columns"])
            writer.writeheader()
            writer.writerows(rows)
        return VALIDATE(self.path, CONTRACT_PATH, verify_snapshot)

    def test_decimal_totals_and_shared_display_names(self):
        other = dict(self.row, ClientId="SYNTHETIC-CLIENT-2", policy_id="SYNTHETIC-POLICY-2", premium="0.20")
        report = self.check_rows([self.row, other])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["premium_total"], "0.30")
        self.assertEqual(report["unique_clients"], 2)

    def test_duplicate_policy_is_rejected(self):
        report = self.check_rows([self.row, self.row])
        self.assertEqual(report["issues"]["duplicate_policy_id"], 1)

    def test_conflicting_industries_within_client_are_rejected(self):
        other = dict(self.row, policy_id="SYNTHETIC-POLICY-2", industry="Minería")
        report = self.check_rows([self.row, other])
        self.assertEqual(report["issues"]["client_industry_conflict"], 1)

    def test_unresolved_is_retained_in_premium_total(self):
        row = dict(self.row, industry="Unresolved", fill_method="unresolved", confidence_level="unresolved")
        report = self.check_rows([row])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["industry_coverage_pct"], 0)
        self.assertEqual(report["premium_total"], "0.10")

    def test_unresolved_cannot_be_disguised_as_original(self):
        report = self.check_rows([dict(self.row, industry="Unresolved")])
        self.assertIn("inconsistent_unresolved_label", report["issues"])

    def test_external_cannot_use_high_confidence(self):
        report = self.check_rows([dict(self.row, fill_method="llm_external")])
        self.assertIn("inconsistent_method_confidence", report["issues"])

    def test_nonfinite_amounts_are_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                report = self.check_rows([dict(self.row, premium=value)])
                self.assertIn("nonfinite_premium", report["issues"])

    def test_reversed_dates_are_rejected(self):
        row = dict(self.row, policy_end_date="2023-12-31")
        self.assertIn("end_before_start", self.check_rows([row])["issues"])

    def test_missing_column_is_rejected(self):
        fields = CONTRACT["columns"][:-1]
        row = {key: value for key, value in self.row.items() if key in fields}
        self.assertIn("schema_mismatch", self.check_rows([row], fields)["issues"])

    def test_malformed_csv_row_is_rejected(self):
        self.check_rows([self.row])
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write("too,few,columns\n")
        report = VALIDATE(self.path, CONTRACT_PATH)
        self.assertIn("malformed_csv_row", report["issues"])

    def test_empty_file_with_header_is_rejected(self):
        self.assertIn("empty_dataset", self.check_rows([])["issues"])

    def test_snapshot_mode_detects_different_input(self):
        report = self.check_rows([self.row], verify_snapshot=True)
        self.assertIn("snapshot_mismatch_sha256", report["issues"])
        self.assertIn("snapshot_mismatch_rows", report["issues"])


if __name__ == "__main__":
    unittest.main()
