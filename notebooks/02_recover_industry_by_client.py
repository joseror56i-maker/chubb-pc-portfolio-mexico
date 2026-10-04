# Databricks notebook source
# MAGIC %md
# MAGIC # Recover industry from the same ClientId
# MAGIC Run after 01. Conflicting original labels stop processing; industry_filled is created explicitly.
# MAGIC Create `config/pipeline.local.json` from the example; paths are resolved relative to that config.

# COMMAND ----------

from pathlib import Path
import os
import sys

# A Git folder or local checkout may start in the notebooks directory.
ROOT = next(
    (
        p
        for p in (Path.cwd(), *Path.cwd().parents)
        if (p / "config/portfolio_contract.json").is_file()
    ),
    None,
)
if ROOT is None:
    raise RuntimeError("Open this notebook inside the complete repository checkout")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.data_processing.runtime import load_config, run_stage

try:
    dbutils.widgets.text("config_path", str(ROOT / "config/pipeline.local.json"))
    CONFIG_PATH = dbutils.widgets.get("config_path")
except NameError:
    CONFIG_PATH = os.environ.get("CHUBB_CONFIG", str(ROOT / "config/pipeline.local.json"))
config = load_config(CONFIG_PATH)

# COMMAND ----------

result = run_stage("recover", config, spark=globals().get("spark"))
print(result)
