"""Meaningful checks of identity, evidence, lineage and the local end-to-end flow."""

import json
import tempfile
import unittest
from pathlib import Path

from src.data_processing.recovery import prepare_raw, recover_by_client
from src.data_processing.external import EVIDENCE_COLUMNS, apply_external, evidence_decision
from src.data_processing.names import canonical_names, build_reporting
from src.data_processing.runtime import (
    ROOT,
    load_config,
    read_csv,
    write_csv,
    run_pipeline,
    run_stage,
)
from src.modeling.diagnostics import correlation_ratio

CONTRACT = json.loads((ROOT / "config/portfolio_contract.json").read_text(encoding="utf-8"))
INDUSTRIES = set(CONTRACT["industry_labels"]) - {"Unresolved"}


def policy(client="001", policy_id="01", industry="Manufactura", name="Empresa SA"):
    return {
        "ClientId": client,
        "policy_id": policy_id,
        "client_name": name,
        "state": "Jalisco",
        "municipality": "Guadalajara",
        "coverage_type": "Property",
        "industry": industry,
        "premium": "0.10",
        "sum_insured": "1000.00",
        "policy_start_date": "2021-01-01",
        "policy_end_date": "2022-01-01",
    }


def evidence(client="002", **changes):
    row = dict.fromkeys(EVIDENCE_COLUMNS, "")
    row.update(
        ClientId=client,
        candidate_industry="Salud",
        entity_found="true",
        entity_confidence="high",
        industry_confidence="high",
        verification_level="official_corporate",
        grounding_sources='["https://example.org/company"]',
    )
    row.update(changes)
    return row


class RecoveryTests(unittest.TestCase):
    def test_same_client_recovery_preserves_originals_and_leading_zero_ids(self):
        raw = prepare_raw([policy(), policy(policy_id="02", industry="")], INDUSTRIES)
        rows = recover_by_client(raw)
        self.assertEqual(rows[1]["industry_filled"], "Manufactura")
        self.assertEqual(rows[1]["industry"], "")
        self.assertEqual([r["fill_method"] for r in rows], ["original", "client_id"])
        self.assertEqual(rows[0]["ClientId"], "001")
        self.assertEqual(rows[1]["premium"], "0.10")

    def test_conflicting_client_labels_fail_instead_of_multiplying_join(self):
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            recover_by_client([policy(), policy(policy_id="02", industry="Salud")])

    def test_reporting_export_cannot_be_used_as_raw(self):
        row = policy()
        row["fill_method"] = "original"
        with self.assertRaisesRegex(ValueError, "original portfolio"):
            prepare_raw([row], INDUSTRIES)

    def test_duplicate_policy_invalid_money_and_dates_are_rejected(self):
        cases = [
            [policy(), policy()],
            [dict(policy(), premium="NaN")],
            [dict(policy(), sum_insured="-1")],
            [dict(policy(), policy_end_date="2020-01-01")],
        ]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                prepare_raw(rows, INDUSTRIES)

    def test_external_acceptance_requires_grounding_and_no_errors(self):
        self.assertEqual(evidence_decision(evidence(), INDUSTRIES), "accepted")
        for change in [
            {"grounding_sources": "[]"},
            {"grounding_sources": "null"},
            {"grounding_sources": "broken"},
            {"error_message": "timeout"},
            {"industry_confidence": "medium"},
            {"candidate_industry": "Unresolved"},
            {"verification_level": "reliable_secondary"},
        ]:
            with self.subTest(change=change):
                self.assertNotEqual(evidence_decision(evidence(**change), INDUSTRIES), "accepted")

    def test_empty_external_cache_abstains_and_source_labels_survive(self):
        recovered = recover_by_client([policy(), policy(client="002", policy_id="02", industry="")])
        filled, _ = apply_external(recovered, [], INDUSTRIES)
        self.assertEqual(filled[1]["industry_final"], "Unresolved")
        self.assertEqual(filled[1]["confidence_level"], "unresolved")
        filled, audit = apply_external(recovered, [evidence()], INDUSTRIES)
        self.assertEqual(filled[1]["industry_final"], "Salud")
        self.assertEqual(filled[1]["industry"], "")
        self.assertEqual(filled[1]["confidence_level"], "medium_low")
        self.assertEqual(audit[0]["grounding_sources"], evidence()["grounding_sources"])

    def test_external_cache_duplicates_and_stale_entries_fail(self):
        recovered = recover_by_client([policy(client="002", industry="")])
        for cache in [[evidence(), evidence()], [evidence(client="other")]]:
            with self.subTest(cache=cache), self.assertRaises(ValueError):
                apply_external(recovered, cache, INDUSTRIES)

    def test_name_family_choice_is_deterministic_and_never_merges_ids(self):
        rows = [
            policy(policy_id="02", name="Árbol SA"),
            policy(policy_id="01", name="Árbol S.A. de C.V."),
            policy(client="002", policy_id="03", name="Árbol SA"),
        ]
        names, lineage = canonical_names(rows)
        self.assertEqual(names["001"], "Árbol S.A. de C.V.")
        self.assertEqual(names["002"], "Árbol SA")
        self.assertEqual((names, lineage), canonical_names(list(reversed(rows))))
        self.assertEqual(lineage[0]["reference_policy_id"], "01")

    def test_invisible_name_characters_are_cleaned_and_lineage_retained(self):
        names, lineage = canonical_names([policy(name="A\u200b\u00a0Empresa\tSA")])
        self.assertEqual(names["001"], "A Empresa SA")
        self.assertIn("\u200b", lineage[0]["reference_raw_name"])

    def test_eta_handles_perfect_null_constant_and_missing_observations(self):
        self.assertEqual(correlation_ratio(["a", "a", "b", "b"], [1, 1, 2, 2]), 1)
        self.assertEqual(correlation_ratio(["a", "b"], [1, 1]), 0)
        self.assertEqual(correlation_ratio(["a", "b"], [None, float("nan")]), 0)
        self.assertEqual(correlation_ratio(["a", "a", "b", "b"], [1, 2, 1, 2]), 0)

    def test_end_to_end_outputs_pass_contract_and_prevent_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            rows = [
                policy(),
                policy(policy_id="02", industry="", name="Empresa S.A."),
                policy(client="002", policy_id="03", industry=""),
            ]
            write_csv(folder / "raw.csv", rows, list(rows[0]))
            config_file = folder / "pipeline.json"
            config_file.write_text(
                json.dumps(
                    {
                        "input_path": "raw.csv",
                        "output_dir": "run",
                        "contract_path": str(ROOT / "config/portfolio_contract.json"),
                    }
                ),
                encoding="utf-8",
            )
            config = load_config(config_file)
            result = run_pipeline(config)
            self.assertEqual(result["report"]["status"], "PASS")
            self.assertEqual(result["report"]["premium_total"], "0.30")
            exported = read_csv(folder / "run/portfolio_reporting.csv")
            self.assertEqual(len(exported), 3)
            self.assertEqual(exported[2]["industry"], "Unresolved")
            self.assertTrue((folder / "run/run_manifest.json").is_file())
            with self.assertRaisesRegex(ValueError, "empty output_dir"):
                run_pipeline(config)

    def test_config_relative_paths_are_independent_of_cwd_and_snapshot_is_protected(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_file = Path(temporary) / "config.json"
            config_file.write_text(
                json.dumps({"input_path": "raw.csv", "output_dir": str(ROOT / "data/processed")}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "snapshot is protected"):
                load_config(config_file)

    def test_individual_stages_refuse_to_mix_existing_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = {
                "output_dir": temporary,
                "contract_path": str(ROOT / "config/portfolio_contract.json"),
            }
            Path(temporary, "02_recovered.csv").write_text("existing result", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Stage outputs already exist"):
                run_stage("recover", config)


if __name__ == "__main__":
    unittest.main()
