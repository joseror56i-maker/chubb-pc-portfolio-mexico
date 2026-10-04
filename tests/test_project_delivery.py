"""Check actual original-data lineage and the downloadable Power BI project."""

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import runpy
import tempfile
import unittest

from src.data_processing.runtime import ROOT, read_csv
from src.data_processing.recovery import prepare_raw, recover_by_client
from src.data_processing.names import canonical_names
from src.data_processing.validate_dashboard import validate_dashboard


class OriginalLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        contract = json.loads((ROOT / "config/portfolio_contract.json").read_text(encoding="utf-8"))
        cls.raw = prepare_raw(read_csv(ROOT / "data/raw/portfolio_original.csv"),
                              set(contract["industry_labels"]) - {"Unresolved"})
        cls.final = {row["policy_id"]: row for row in read_csv(ROOT / "data/processed/portfolio_reporting.csv")}
        cls.recovered = recover_by_client(cls.raw)

    def test_policy_identity_money_dates_and_original_industries_survive(self):
        self.assertEqual(set(self.final), {row["policy_id"] for row in self.raw})
        for original in self.raw:
            final = self.final[original["policy_id"]]
            for field in ("ClientId", "state", "municipality", "coverage_type", "policy_start_date", "policy_end_date"):
                self.assertEqual(original[field], final[field])
            for field in ("premium", "sum_insured"):
                self.assertEqual(Decimal(original[field]), Decimal(final[field]))
            if original["industry"]:
                self.assertEqual(original["industry"], final["industry"])
                self.assertEqual(final["fill_method"], "original")

    def test_same_client_assignments_match_the_submitted_dataset(self):
        filled = [row for row in self.recovered if row["fill_method"] == "client_id"]
        self.assertEqual(len(filled), 16159)
        for row in filled:
            self.assertEqual(row["industry_filled"], self.final[row["policy_id"]]["industry"])
            self.assertEqual(row["fill_method"], self.final[row["policy_id"]]["fill_method"])

    def test_display_names_reproduce_from_original_variants(self):
        names, _ = canonical_names(self.raw)
        self.assertTrue(all(names[row["ClientId"]] == row["client_name"] for row in self.final.values()))


class DashboardDeliveryTests(unittest.TestCase):
    def test_complete_project_references_are_valid(self):
        result = validate_dashboard(ROOT / "dashboard/premium_growth.pbip")
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["pages"], 2)
        self.assertEqual(result["tables"], 12)

    def test_downloading_only_the_pbip_is_detected_as_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "premium_growth.pbip"
            path.write_bytes((ROOT / "dashboard/premium_growth.pbip").read_bytes())
            self.assertEqual(validate_dashboard(path)["status"], "FAIL")

    def test_local_setup_preserves_shared_model_and_copies_dependencies(self):
        expression = ROOT / "dashboard/premium_growth.SemanticModel/definition/expressions.tmdl"
        original_hash = hashlib.sha256(expression.read_bytes()).hexdigest()
        module = runpy.run_path(str(ROOT / "dashboard/setup_dashboard.py"))
        with tempfile.TemporaryDirectory() as temporary:
            project = module["prepare_dashboard"](ROOT / "data/processed/portfolio_reporting.csv", Path(temporary) / "pbi")
            self.assertEqual(validate_dashboard(project)["status"], "PASS")
            configured = project.parent / "premium_growth.SemanticModel/definition/expressions.tmdl"
            self.assertIn((ROOT / "data/processed/portfolio_reporting.csv").as_posix(), configured.read_text(encoding="utf-8"))
        self.assertEqual(original_hash, hashlib.sha256(expression.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
