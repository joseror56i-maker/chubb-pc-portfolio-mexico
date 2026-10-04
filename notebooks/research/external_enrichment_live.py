# Databricks notebook source
# MAGIC %md
# MAGIC # Optional live external research
# MAGIC This notebook sends company names and locations to `ai_enrich` with web search.
# MAGIC It incurs service usage, needs an enabled workspace and compatible runtime, and
# MAGIC produces new evidence rather than reproducing historical web responses.
# MAGIC First use `backtest`; inspect its saved results before choosing `production`.
# MAGIC Accepted candidates are still `medium_low`, never calibrated/high truth.
# MAGIC Enable `allow_live_enrichment` in your private config to execute.

# COMMAND ----------

import random
import sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = next(
    (
        p
        for p in (Path.cwd(), *Path.cwd().parents)
        if (p / "config/portfolio_contract.json").is_file()
    ),
    None,
)
if ROOT is None:
    raise RuntimeError("Open the complete repository in a Databricks Git folder")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.data_processing.runtime import load_config, read_csv, write_json
from src.data_processing.external import evidence_decision
from src.enrichment.prompt import INDUSTRIES
from src.enrichment.service import research_run

dbutils.widgets.text("config_path", str(ROOT / "config/pipeline.local.json"))
dbutils.widgets.dropdown("mode", "backtest", ["backtest", "production"])
config = load_config(dbutils.widgets.get("config_path"))
if config.get("allow_live_enrichment") is not True:
    raise RuntimeError(
        "Live research is disabled. Set allow_live_enrichment=true in your private config to run"
    )
mode = dbutils.widgets.get("mode")
if not config.get("live_output_dir"):
    raise ValueError("Set live_output_dir to a fresh absolute Unity Catalog Volume directory")
live_output = Path(config["live_output_dir"])
if not live_output.is_absolute() or not str(live_output).startswith("/Volumes/"):
    raise ValueError("live_output_dir must be an absolute /Volumes/... path")
rows = read_csv(Path(config["output_dir"]) / "02_recovered.csv")

# COMMAND ----------

# Backtest selection is at client level, uses original targets, and sends exactly
# the same context fields as production. No industry/ClientId enters the payload.
if mode == "backtest":
    by_industry = defaultdict(dict)
    for row in rows:
        if row["fill_method"] == "original":
            by_industry[row["industry"]][row["ClientId"]] = row["industry"]
    rng = random.Random(42)
    truth = {}
    for industry, clients in sorted(by_industry.items()):
        selected = rng.sample(sorted(clients), min(3, len(clients)))
        truth.update({client: industry for client in selected})
    research_rows = [row for row in rows if row["ClientId"] in truth]
else:
    truth = {}
    research_rows = [row for row in rows if row["fill_method"] == "unresolved"]

results = research_run(
    spark, research_rows, live_output, batch_size=int(config.get("external_batch_size", 50))
)

# COMMAND ----------

# Use the same rule as the replay pipeline; the old notebook relaxed production
# acceptance after evaluating a stricter backtest. No such relaxation happens here.
decisions = Counter(evidence_decision(row, set(INDUSTRIES)) for row in results)
accepted = [row for row in results if evidence_decision(row, set(INDUSTRIES)) == "accepted"]
summary = {
    "mode": mode,
    "clients": len(results),
    "decisions": dict(decisions),
    "accepted_clients": len(accepted),
    "seed": 42,
    "acceptance_rule": "high/high + official + grounded + no error + taxonomy",
}
if mode == "backtest":
    correct = sum(row["candidate_industry"] == truth[row["ClientId"]] for row in accepted)
    summary.update(
        correct_accepted_clients=correct,
        accepted_accuracy=correct / len(accepted) if accepted else None,
    )
write_json(live_output / "research_summary.json", summary)
print(summary)

# MAGIC %md
# MAGIC Production output is a candidate cache. Review evidence and errors, then set
# MAGIC `external_results_path` to that CSV in a fresh pipeline run. Never use a
# MAGIC backtest cache to fill unresolved clients. The replay step rejects stale IDs.
