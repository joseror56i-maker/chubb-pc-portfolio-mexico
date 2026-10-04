# Databricks notebook source
# Importar librerias y funciones necesarias para el analisis
from pyspark.sql import functions as F
from pyspark.sql.window import Window

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

if not config.get("input_table"):
    raise ValueError("This optional distributed EDA uses input_table; use 01 for local CSV EDA")
df = spark.table(config["input_table"])

display(df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Dataset overview

# COMMAND ----------

df.count(), len(df.columns)

# COMMAND ----------

df.printSchema()

# COMMAND ----------

display(
    df.select(
        F.countDistinct("ClientId").alias("clients"),
        F.countDistinct("industry").alias("industries"),
        F.countDistinct("state").alias("states"),
        F.countDistinct("municipality").alias("municipalities"),
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ##Missing Values

# COMMAND ----------

total_rows = df.count()

nulls = df.select([sum(F.when(F.col(c).isNull(), 1).otherwise(0)).alias(c) for c in df.columns])

display(nulls)

# COMMAND ----------

# MAGIC %md
# MAGIC ##Distribution Analysis

# COMMAND ----------

display(
    df.agg(F.count("*").alias("records"), F.countDistinct("policy_id").alias("unique_policies"))
)

# COMMAND ----------

display(
    df.groupBy("industry")
    .agg(F.count("*").alias("records"), F.sum("premium").alias("premium"))
    .orderBy(F.desc("premium"))
)

# COMMAND ----------

display(df.select("premium").summary("count", "mean", "stddev", "min", "25%", "50%", "75%", "max"))

# COMMAND ----------

display(
    df.groupBy("state")
    .agg(F.count("*").alias("records"), F.sum("premium").alias("premium"))
    .orderBy(F.desc("premium"))
)

# COMMAND ----------

display(
    df.groupBy("municipality")
    .agg(F.count("*").alias("records"), F.sum("premium").alias("premium"))
    .orderBy(F.desc("premium"))
)

# COMMAND ----------

df = df.withColumn("year", F.year("policy_start_date"))

# COMMAND ----------

display(
    df.groupBy("year")
    .agg(F.count("*").alias("records"), F.sum("premium").alias("premium"))
    .orderBy("year")
)

# COMMAND ----------

clients = df.groupBy("ClientId").agg(F.count("*").alias("records"))

# COMMAND ----------

display(clients.orderBy(F.desc("records")))

# COMMAND ----------

client_industry = (
    df.filter(F.col("industry").isNotNull())
    .groupBy("ClientId")
    .agg(
        F.countDistinct("industry").alias("n_industries"),
        F.first("industry").alias("known_industry"),
    )
)

# COMMAND ----------

unambiguous_clients = client_industry.filter(F.col("n_industries") == 1)

# COMMAND ----------

recoverable = df.filter(F.col("industry").isNull()).join(
    unambiguous_clients, on="ClientId", how="left"
)

# COMMAND ----------

display(
    recoverable.agg(
        F.count("*").alias("missing_records"),
        sum(F.when(F.col("known_industry").isNotNull(), 1).otherwise(0)).alias(
            "recoverable_records"
        ),
    )
)

# COMMAND ----------

display(client_industry.filter(F.col("n_industries") > 1).orderBy(F.desc("n_industries")))

# COMMAND ----------

display(
    recoverable.agg(
        F.count("*").alias("missing_records"),
        sum(F.when(F.col("known_industry").isNotNull(), 1).otherwise(0)).alias(
            "recoverable_records"
        ),
        sum(F.when(F.col("known_industry").isNull(), 1).otherwise(0)).alias("unresolved_records"),
    ).withColumn(
        "recovery_pct", round(F.col("recoverable_records") / F.col("missing_records") * 100, 2)
    )
)

# COMMAND ----------

display(
    client_industry.groupBy("n_industries")
    .agg(F.count("*").alias("clients"))
    .orderBy("n_industries")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Nulls By Client

# COMMAND ----------
