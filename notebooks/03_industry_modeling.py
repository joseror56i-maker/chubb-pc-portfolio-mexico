# Databricks notebook source
# MAGIC %md
# MAGIC # Industry Imputation — Machine Learning Validation
# MAGIC
# MAGIC **Objective:** determine whether the variables available in the portfolio contain enough out-of-sample signal to infer `industry` for previously unseen clients.
# MAGIC
# MAGIC This notebook intentionally excludes the general EDA performed elsewhere. It focuses on:
# MAGIC
# MAGIC 1. client-level feature engineering,
# MAGIC 2. pre-model statistical diagnostics,
# MAGIC 3. supervised model benchmarking,
# MAGIC 4. alternative/robustness experiments,
# MAGIC 5. final holdout validation,
# MAGIC 6. a defensible decision on whether ML should be used for automatic imputation.
# MAGIC
# MAGIC **Important:** only the original non-null `industry` labels are used as modeling ground truth. Labels filled by ClientId or LLM enrichment are never used as training targets.
# MAGIC

# COMMAND ----------


# MAGIC %md
# MAGIC **Review:** historical scores are not reproduced here. Holdout isolation, fold scaling, deterministic ordering and missing eta calculation were corrected. Early-stopping CV scores are development diagnostics. No predictions enter reporting.
# MAGIC
# MAGIC ## 1. Libraries and configuration
# MAGIC

# COMMAND ----------

# MAGIC Install the optional versions in `requirements-modeling.txt` before running this research notebook.
# MAGIC

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

import re
import unicodedata
import numpy as np
import pandas as pd

from scipy.stats import chi2_contingency, ks_2samp

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import mutual_info_classif
from sklearn.impute import SimpleImputer
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    log_loss,
    top_k_accuracy_score,
    roc_auc_score,
    adjusted_mutual_info_score,
)
from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    StratifiedGroupKFold,
    GroupShuffleSplit,
    cross_val_predict,
    cross_val_score,
)
from sklearn.pipeline import Pipeline, make_pipeline, make_union
from sklearn.preprocessing import OneHotEncoder, LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from lightgbm import LGBMClassifier, early_stopping
from xgboost import XGBClassifier
from catboost import CatBoostClassifier
from sklearn.cluster import KMeans

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
MODELING_OUTPUT = Path(config["output_dir"]) / "03_modeling"
if MODELING_OUTPUT.exists():
    raise ValueError("Modeling outputs already exist; use a fresh run directory")

# Use the recovered stage before external enrichment. The source industry column
# remains untouched; only original non-null labels become modeling targets.
if "spark" not in globals():
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.appName("chubb-industry-research").getOrCreate()
DATA_PATH = str(Path(config["output_dir"]) / "02_recovered.csv")
df = spark.read.option("header", True).csv(DATA_PATH)
for field in ("premium", "sum_insured"):
    df = df.withColumn(field, F.col(field).cast("decimal(38,6)"))
for field in ("policy_start_date", "policy_end_date"):
    df = df.withColumn(field, F.col(field).cast("date"))
from src.modeling.diagnostics import correlation_ratio

if "display" not in globals():

    def display(value):
        print(value)


required_columns = {
    "ClientId",
    "client_name",
    "state",
    "municipality",
    "coverage_type",
    "industry",
    "premium",
    "sum_insured",
    "policy_start_date",
    "policy_end_date",
    "fill_method",
}

missing_columns = required_columns - set(df.columns)

assert not missing_columns, f"Missing required columns: {sorted(missing_columns)}"

print("Rows:", df.count())
print("Columns:", len(df.columns))


# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Client-level feature engineering
# MAGIC
# MAGIC `industry` behaves as a client attribute in the labeled portion of the portfolio, so modeling is performed at **one row per `ClientId`**.
# MAGIC
# MAGIC Features summarize:
# MAGIC - premium and sum insured,
# MAGIC - policy duration and portfolio tenure,
# MAGIC - geographic concentration,
# MAGIC - number of coverages,
# MAGIC - coverage mix.
# MAGIC
# MAGIC The target is built **only from original industry labels**.
# MAGIC

# COMMAND ----------

df_ml = df.withColumn(
    "policy_duration_days", F.datediff(F.col("policy_end_date"), F.col("policy_start_date"))
)


# COMMAND ----------

client_target = (
    df_ml.filter((F.col("industry").isNotNull() & (F.col("fill_method") == "original")))
    .groupBy("ClientId")
    .agg(F.first("industry", ignorenulls=True).alias("industry"))
)

client_numeric = (
    df_ml.groupBy("ClientId")
    .agg(
        F.count("*").alias("policy_count"),
        F.avg("premium").alias("avg_premium"),
        F.sum("premium").alias("total_premium"),
        F.avg("sum_insured").alias("avg_sum_insured"),
        F.sum("sum_insured").alias("total_sum_insured"),
        F.avg("policy_duration_days").alias("avg_policy_duration_days"),
        F.countDistinct("coverage_type").alias("n_coverages"),
        F.countDistinct("state").alias("n_states"),
        F.countDistinct("municipality").alias("n_municipalities"),
        F.min("policy_start_date").alias("first_policy_date"),
        F.max("policy_end_date").alias("last_policy_date"),
    )
    .withColumn(
        "premium_si_ratio",
        F.when(F.col("total_sum_insured") > 0, F.col("total_premium") / F.col("total_sum_insured")),
    )
    .withColumn(
        "portfolio_span_days", F.datediff(F.col("last_policy_date"), F.col("first_policy_date"))
    )
)


# COMMAND ----------


def get_main_category(dataframe, column_name, new_name):
    counts = (
        dataframe.filter(F.col(column_name).isNotNull()).groupBy("ClientId", column_name).count()
    )

    w = Window.partitionBy("ClientId").orderBy(F.desc("count"), F.asc(column_name))

    return (
        counts.withColumn("rn", F.row_number().over(w))
        .filter(F.col("rn") == 1)
        .select("ClientId", F.col(column_name).alias(new_name))
    )


main_state = get_main_category(df_ml, "state", "main_state")

main_municipality = get_main_category(df_ml, "municipality", "main_municipality")


# COMMAND ----------

coverage_values = sorted(
    [
        row["coverage_type"]
        for row in (
            df_ml.select("coverage_type")
            .filter(F.col("coverage_type").isNotNull())
            .distinct()
            .collect()
        )
    ]
)

coverage_mix = (
    df_ml.filter(F.col("coverage_type").isNotNull())
    .groupBy("ClientId")
    .pivot("coverage_type", coverage_values)
    .count()
    .fillna(0)
)

used_names = set()

for old_name in coverage_mix.columns:

    if old_name == "ClientId":
        continue

    clean_name = re.sub(r"[^a-zA-Z0-9]+", "_", old_name).strip("_").lower()

    new_name = f"coverage_share_{clean_name}"
    counter = 1

    while new_name in used_names:
        counter += 1
        new_name = f"coverage_share_" f"{clean_name}_{counter}"

    used_names.add(new_name)

    coverage_mix = coverage_mix.withColumnRenamed(old_name, new_name)

coverage_columns = [c for c in coverage_mix.columns if c != "ClientId"]

coverage_mix = coverage_mix.join(
    client_numeric.select("ClientId", "policy_count"), on="ClientId", how="left"
)

for c in coverage_columns:
    coverage_mix = coverage_mix.withColumn(c, F.col(c) / F.col("policy_count"))

coverage_mix = coverage_mix.drop("policy_count")


# COMMAND ----------

client_features = (
    client_numeric.join(main_state, on="ClientId", how="left")
    .join(main_municipality, on="ClientId", how="left")
    .join(coverage_mix, on="ClientId", how="left")
)

client_labeled = client_features.join(client_target, on="ClientId", how="inner")

unresolved_ids = df_ml.filter(F.col("fill_method") == "unresolved").select("ClientId").distinct()

client_unresolved = client_features.join(unresolved_ids, on="ClientId", how="inner")

print("Labeled clients:", client_labeled.count())
print("Unresolved clients:", client_unresolved.count())


# COMMAND ----------

categorical_features = ["main_state", "main_municipality"]

numeric_features = [
    "policy_count",
    "avg_premium",
    "total_premium",
    "avg_sum_insured",
    "total_sum_insured",
    "premium_si_ratio",
    "avg_policy_duration_days",
    "portfolio_span_days",
    "n_coverages",
    "n_states",
    "n_municipalities",
] + coverage_columns

features = categorical_features + numeric_features

model_pd = (
    client_labeled.select(["ClientId"] + features + ["industry"]).orderBy("ClientId").toPandas()
)

# Spark Decimal columns preserve money upstream. ML needs finite numeric arrays;
# this conversion is limited to research features and never changes reporting money.
model_pd[numeric_features] = model_pd[numeric_features].apply(pd.to_numeric, errors="raise")
all_model_client_ids = model_pd["ClientId"].copy()

X = model_pd[features].copy()
y = model_pd["industry"].copy()
groups = model_pd["ClientId"].copy()

# Reserve holdout BEFORE target diagnostics or feature/model choices.
# All robustness experiments below are restricted to development clients.
X_dev, X_test, y_dev, y_test = train_test_split(X, y, test_size=0.20, stratify=y, random_state=42)
development_ids = model_pd.loc[X_dev.index, "ClientId"].tolist()
X = X_dev
y = y_dev
groups = groups.loc[X_dev.index]
model_pd = model_pd.loc[X_dev.index].copy()
df_development = df_ml.filter(F.col("ClientId").isin(development_ids))

print("Development clients:", len(model_pd))
print("Features:", len(features))
print("Industries:", y.nunique())


# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Pre-model diagnostics
# MAGIC
# MAGIC These checks are performed **before** selecting a model.
# MAGIC
# MAGIC The goal is not to prove that prediction is impossible from correlations alone. The goal is to quantify whether the supplied predictors show any useful relationship with `industry` and whether the unresolved population resembles the labeled population.
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 Target distribution and naive baselines
# MAGIC

# COMMAND ----------

target_distribution = y.value_counts().rename_axis("industry").reset_index(name="clients")

target_distribution["share"] = target_distribution["clients"] / target_distribution["clients"].sum()

n_classes = y.nunique()

majority_accuracy_baseline = y.value_counts(normalize=True).iloc[0]

random_balanced_baseline = 1 / n_classes
random_top2_baseline = 2 / n_classes
random_top3_baseline = 3 / n_classes

prior = y.value_counts(normalize=True).sort_index()

prior_logloss_baseline = -np.sum(prior.values * np.log(prior.values))

display(target_distribution)

print(f"Majority accuracy baseline: " f"{majority_accuracy_baseline:.4f}")

print(f"Random balanced-accuracy baseline: " f"{random_balanced_baseline:.4f}")

print(f"Random top-2 baseline: " f"{random_top2_baseline:.4f}")

print(f"Random top-3 baseline: " f"{random_top3_baseline:.4f}")

print(f"Empirical-prior log-loss baseline: " f"{prior_logloss_baseline:.4f}")


# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 Numerical redundancy
# MAGIC
# MAGIC Spearman correlation is calculated **between numerical predictors only**.
# MAGIC No Pearson/Spearman correlation is calculated against integer-encoded `industry`, because `industry` is nominal and has no natural numeric order.
# MAGIC

# COMMAND ----------

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

# =========================================================
# DATA FOR CORRELATION ANALYSIS
# =========================================================

X_corr = X.reset_index(drop=True).copy()

y_corr = y.reset_index(drop=True).copy()


core_numeric_candidates = [
    "policy_count",
    "avg_premium",
    "total_premium",
    "avg_sum_insured",
    "total_sum_insured",
    "premium_si_ratio",
    "avg_policy_duration_days",
    "portfolio_span_days",
    "n_coverages",
    "n_states",
    "n_municipalities",
]


# Remove constant features automatically
constant_features = [
    feature for feature in core_numeric_candidates if X_corr[feature].nunique(dropna=True) <= 1
]


core_numeric_features = [
    feature for feature in core_numeric_candidates if feature not in constant_features
]


coverage_features = [c for c in X_corr.columns if c.startswith("coverage_share_")]


print("Excluded constant features:", constant_features)

# COMMAND ----------

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

core_numeric_candidates = [
    "policy_count",
    "avg_premium",
    "total_premium",
    "avg_sum_insured",
    "total_sum_insured",
    "premium_si_ratio",
    "avg_policy_duration_days",
    "portfolio_span_days",
    "n_coverages",
    "n_states",
    "n_municipalities",
]


# Remove constant variables
core_numeric_features = [
    feature for feature in core_numeric_candidates if X[feature].nunique(dropna=True) > 1
]


FEATURE_LABELS = {
    "policy_count": "Policy count",
    "avg_premium": "Average premium",
    "total_premium": "Total premium",
    "avg_sum_insured": "Average sum insured",
    "total_sum_insured": "Total sum insured",
    "premium_si_ratio": "Premium / SI",
    "avg_policy_duration_days": "Average policy duration",
    "portfolio_span_days": "Portfolio span",
    "n_coverages": "Number of coverages",
}


def display_name(feature):

    if feature in FEATURE_LABELS:
        return FEATURE_LABELS[feature]

    if feature.startswith("coverage_share_"):

        return feature.replace("coverage_share_", "").replace("_", " ").title()

    return feature


# COMMAND ----------

numeric_corr = X[core_numeric_features].corr(method="spearman")


fig, ax = plt.subplots(figsize=(11, 9))

image = ax.imshow(numeric_corr.values, vmin=-1, vmax=1, cmap="coolwarm")


ax.set_xticks(range(len(numeric_corr.columns)))

ax.set_yticks(range(len(numeric_corr.index)))


ax.set_xticklabels([display_name(c) for c in numeric_corr.columns], rotation=45, ha="right")

ax.set_yticklabels([display_name(c) for c in numeric_corr.index])


# Show EVERY value
for i in range(len(numeric_corr.index)):

    for j in range(len(numeric_corr.columns)):

        value = numeric_corr.iloc[i, j]

        if not pd.isna(value):

            ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=8)


ax.set_title("Spearman Correlation Between Portfolio Features", fontsize=14, pad=15)


colorbar = fig.colorbar(image, ax=ax, shrink=0.85)

colorbar.set_label("Spearman correlation")


plt.tight_layout()
plt.show()

# COMMAND ----------

industry_corr = pd.DataFrame(
    index=[display_name(feature) for feature in core_numeric_features],
    columns=["Industry"],
    dtype=float,
)

for feature in core_numeric_features:

    industry_corr.loc[display_name(feature), "Industry"] = correlation_ratio(y, X[feature])

# COMMAND ----------

industry_corr = pd.DataFrame(
    index=[display_name(feature) for feature in core_numeric_features],
    columns=["Industry"],
    dtype=float,
)

for feature in core_numeric_features:

    industry_corr.loc[display_name(feature), "Industry"] = correlation_ratio(y, X[feature])

# COMMAND ----------

fig, ax = plt.subplots(figsize=(5, 7))

image = ax.imshow(
    industry_corr.values,
    vmin=0,
    vmax=max(0.10, industry_corr["Industry"].max()),
    cmap="Reds",
    aspect="auto",
)

ax.set_xticks([0])

ax.set_xticklabels(["Industry"])

ax.set_yticks(range(len(industry_corr.index)))

ax.set_yticklabels(industry_corr.index)

for i in range(len(industry_corr.index)):

    value = industry_corr.iloc[i, 0]

    ax.text(0, i, f"{value:.3f}", ha="center", va="center", fontsize=9)

ax.set_title("Association Between Portfolio Features and Industry", fontsize=14, pad=15)

colorbar = fig.colorbar(image, ax=ax, shrink=0.85)

colorbar.set_label("Correlation Ratio (η)")

plt.tight_layout()
plt.show()

# COMMAND ----------

coverage_corr = pd.DataFrame(
    index=[display_name(feature) for feature in coverage_features],
    columns=["Industry"],
    dtype=float,
)

for feature in coverage_features:

    coverage_corr.loc[display_name(feature), "Industry"] = correlation_ratio(y, X[feature])

# COMMAND ----------

fig, ax = plt.subplots(figsize=(5, 6))

image = ax.imshow(
    coverage_corr.values,
    vmin=0,
    vmax=max(0.10, coverage_corr["Industry"].max()),
    cmap="Reds",
    aspect="auto",
)

ax.set_xticks([0])

ax.set_xticklabels(["Industry"])

ax.set_yticks(range(len(coverage_corr.index)))

ax.set_yticklabels(coverage_corr.index)

for i in range(len(coverage_corr.index)):

    value = coverage_corr.iloc[i, 0]

    ax.text(0, i, f"{value:.3f}", ha="center", va="center", fontsize=9)

ax.set_title("Association Between Coverage Mix and Industry", fontsize=14, pad=15)

colorbar = fig.colorbar(image, ax=ax, shrink=0.85)

colorbar.set_label("Correlation Ratio (η)")

plt.tight_layout()
plt.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.3 Categorical association with `industry`
# MAGIC

# COMMAND ----------

# Restore Python built-in min (shadowed by pyspark.sql.functions.min)


def cramers_v_corrected(x, y):

    table = pd.crosstab(x, y)

    chi2 = chi2_contingency(table, correction=False)[0]

    n = table.to_numpy().sum()

    if n <= 1:
        return np.nan

    phi2 = chi2 / n

    r, k = table.shape

    phi2_corr = max(0, phi2 - ((k - 1) * (r - 1)) / (n - 1))

    r_corr = r - ((r - 1) ** 2) / (n - 1)

    k_corr = k - ((k - 1) ** 2) / (n - 1)

    denominator = min(k_corr - 1, r_corr - 1)

    if denominator <= 0:
        return 0.0

    return np.sqrt(phi2_corr / denominator)


categorical_association = pd.DataFrame(
    [
        {
            "feature": "main_state",
            "cramers_v": cramers_v_corrected(model_pd["main_state"], model_pd["industry"]),
        },
        {
            "feature": "main_municipality",
            "cramers_v": cramers_v_corrected(model_pd["main_municipality"], model_pd["industry"]),
        },
    ]
)

policy_labeled_pd = (
    df_development.filter((F.col("industry").isNotNull() & (F.col("fill_method") == "original")))
    .select("coverage_type", "industry")
    .orderBy("ClientId")
    .toPandas()
)

coverage_v = cramers_v_corrected(policy_labeled_pd["coverage_type"], policy_labeled_pd["industry"])

categorical_association = pd.concat(
    [
        categorical_association,
        pd.DataFrame([{"feature": "coverage_type_policy_level", "cramers_v": coverage_v}]),
    ],
    ignore_index=True,
)

display(categorical_association.sort_values("cramers_v", ascending=False))


# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.4 Mutual information with permutation null
# MAGIC
# MAGIC Mutual Information can detect non-linear dependence that ordinary correlation can miss.
# MAGIC
# MAGIC Observed MI is compared against a permutation-based null distribution. The threshold uses the 95th percentile of the **maximum null MI within each feature family**, making the check conservative against multiple comparisons.
# MAGIC

# COMMAND ----------


def mutual_information_with_null(matrix, target, discrete, n_permutations=100, seed=42):

    matrix = matrix.replace([np.inf, -np.inf], np.nan).copy()

    for c in matrix.columns:
        if matrix[c].isna().any():
            matrix[c] = matrix[c].fillna(matrix[c].median())

    observed = mutual_info_classif(matrix, target, discrete_features=discrete, random_state=seed)

    rng = np.random.default_rng(seed)

    null_results = []

    for i in range(n_permutations):

        y_perm = rng.permutation(target)

        null_results.append(
            mutual_info_classif(
                matrix, y_perm, discrete_features=discrete, random_state=seed + i + 1
            )
        )

    null_results = np.array(null_results)

    family_threshold = np.percentile(null_results.max(axis=1), 95)

    return pd.DataFrame(
        {
            "feature": matrix.columns,
            "mutual_information": observed,
            "null_p95_family_max": family_threshold,
            "signal": observed > family_threshold,
        }
    ).sort_values("mutual_information", ascending=False)


y_mi = pd.factorize(y)[0]

continuous_mi_features = [
    "avg_premium",
    "total_premium",
    "avg_sum_insured",
    "total_sum_insured",
    "premium_si_ratio",
    "avg_policy_duration_days",
    "portfolio_span_days",
] + coverage_columns

discrete_mi_features = ["policy_count", "n_coverages", "n_states", "n_municipalities"]

mi_continuous = mutual_information_with_null(X[continuous_mi_features], y_mi, discrete=False)

mi_discrete = mutual_information_with_null(X[discrete_mi_features], y_mi, discrete=True)

display(mi_continuous)
display(mi_discrete)


# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.5 Labeled vs. unresolved population shift
# MAGIC
# MAGIC A model trained on labeled clients would be deployed on unresolved clients. Numerical distributions are compared with the Kolmogorov-Smirnov statistic.
# MAGIC
# MAGIC Large differences are an additional warning against extrapolating model performance to the unresolved population.
# MAGIC

# COMMAND ----------

unresolved_pd = (
    client_unresolved.orderBy("ClientId")
    .select(*[F.col(c).cast("double").alias(c) for c in numeric_features])
    .toPandas()
)

shift_rows = []

for feature in numeric_features:

    labeled_values = model_pd[feature].replace([np.inf, -np.inf], np.nan).dropna()

    unresolved_values = unresolved_pd[feature].replace([np.inf, -np.inf], np.nan).dropna()

    if len(labeled_values) > 0 and len(unresolved_values) > 0:

        ks_result = ks_2samp(labeled_values, unresolved_values)

        shift_rows.append(
            {
                "feature": feature,
                "median_labeled": labeled_values.median(),
                "median_unresolved": unresolved_values.median(),
                "ks_statistic": ks_result.statistic,
                "p_value": ks_result.pvalue,
            }
        )

shift_summary = pd.DataFrame(
    shift_rows,
    columns=["feature", "median_labeled", "median_unresolved", "ks_statistic", "p_value"],
).sort_values("ks_statistic", ascending=False)

display(shift_summary)


# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Train / test design
# MAGIC
# MAGIC - **80% development set** for model selection and 5-fold stratified cross-validation.
# MAGIC - **20% untouched holdout** used only after model comparison.
# MAGIC - Because the modeling table contains one row per client, client leakage between train and validation is avoided by construction.
# MAGIC

# COMMAND ----------

# The holdout was reserved before section 3; never resplit it here.

label_encoder = LabelEncoder()

y_dev_encoded = label_encoder.fit_transform(y_dev)

y_test_encoded = label_encoder.transform(y_test)

n_classes = len(label_encoder.classes_)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

print("Development:", X_dev.shape)
print("Holdout:", X_test.shape)
print("Classes:", n_classes)


# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Shared preprocessing and metrics
# MAGIC

# COMMAND ----------


def build_preprocessor():

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    numeric_pipeline = Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))])

    return ColumnTransformer(
        transformers=[
            ("categorical", categorical_pipeline, categorical_features),
            ("numeric", numeric_pipeline, numeric_features),
        ]
    )


def calculate_metrics(y_true, y_pred, y_proba):

    labels = np.arange(n_classes)

    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "precision_macro": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "recall_macro": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_weighted": f1_score(y_true, y_pred, average="weighted", zero_division=0),
        "log_loss": log_loss(y_true, y_proba, labels=labels),
        "top_2_accuracy": top_k_accuracy_score(y_true, y_proba, k=2, labels=labels),
        "top_3_accuracy": top_k_accuracy_score(y_true, y_proba, k=3, labels=labels),
    }


# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Supervised benchmark
# MAGIC
# MAGIC Three different tree-based model families are evaluated under the same 5-fold CV framework:
# MAGIC
# MAGIC - LightGBM
# MAGIC - XGBoost
# MAGIC - CatBoost
# MAGIC
# MAGIC Class-balanced sample weights are used because the target distribution is uneven.
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ### 6.1 LightGBM
# MAGIC

# COMMAND ----------


def run_lightgbm_cv():

    results = []
    best_iterations = []

    for fold, (train_idx, valid_idx) in enumerate(cv.split(X_dev, y_dev_encoded), start=1):

        X_train = X_dev.iloc[train_idx].copy()

        X_valid = X_dev.iloc[valid_idx].copy()

        y_train = y_dev_encoded[train_idx]

        y_valid = y_dev_encoded[valid_idx]

        preprocessor = build_preprocessor()

        X_train_processed = preprocessor.fit_transform(X_train)

        X_valid_processed = preprocessor.transform(X_valid)

        sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)

        model = LGBMClassifier(
            objective="multiclass",
            n_estimators=2000,
            learning_rate=0.03,
            num_leaves=31,
            max_depth=-1,
            min_child_samples=20,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            verbosity=-1,
        )

        model.fit(
            X_train_processed,
            y_train,
            sample_weight=sample_weight,
            eval_set=[(X_valid_processed, y_valid)],
            eval_metric="multi_logloss",
            callbacks=[early_stopping(100, verbose=False)],
        )

        pred = model.predict(X_valid_processed)

        proba = model.predict_proba(X_valid_processed)

        fold_metrics = calculate_metrics(y_valid, pred, proba)

        fold_metrics["fold"] = fold

        results.append(fold_metrics)

        best_iterations.append(model.best_iteration_)

    return (pd.DataFrame(results), best_iterations)


lgbm_results, lgbm_iterations = run_lightgbm_cv()


# COMMAND ----------

# MAGIC %md
# MAGIC ### 6.2 XGBoost
# MAGIC

# COMMAND ----------


def run_xgboost_cv():

    results = []
    best_iterations = []

    for fold, (train_idx, valid_idx) in enumerate(cv.split(X_dev, y_dev_encoded), start=1):

        X_train = X_dev.iloc[train_idx].copy()

        X_valid = X_dev.iloc[valid_idx].copy()

        y_train = y_dev_encoded[train_idx]

        y_valid = y_dev_encoded[valid_idx]

        preprocessor = build_preprocessor()

        X_train_processed = preprocessor.fit_transform(X_train)

        X_valid_processed = preprocessor.transform(X_valid)

        sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)

        model = XGBClassifier(
            objective="multi:softprob",
            num_class=n_classes,
            n_estimators=2000,
            learning_rate=0.03,
            max_depth=6,
            min_child_weight=3,
            subsample=0.8,
            colsample_bytree=0.8,
            gamma=0.05,
            reg_alpha=0.1,
            reg_lambda=1.0,
            tree_method="hist",
            eval_metric="mlogloss",
            early_stopping_rounds=100,
            random_state=42,
            n_jobs=-1,
        )

        model.fit(
            X_train_processed,
            y_train,
            sample_weight=sample_weight,
            eval_set=[(X_valid_processed, y_valid)],
            verbose=False,
        )

        pred = model.predict(X_valid_processed)

        proba = model.predict_proba(X_valid_processed)

        fold_metrics = calculate_metrics(y_valid, pred, proba)

        fold_metrics["fold"] = fold

        results.append(fold_metrics)

        best_iterations.append(model.best_iteration + 1)

    return (pd.DataFrame(results), best_iterations)


xgb_results, xgb_iterations = run_xgboost_cv()


# COMMAND ----------

# MAGIC %md
# MAGIC ### 6.3 CatBoost
# MAGIC

# COMMAND ----------


def prepare_catboost(dataframe):

    dataframe = dataframe.copy()

    for column in categorical_features:

        dataframe[column] = dataframe[column].fillna("Unknown").astype(str)

    for column in numeric_features:

        dataframe[column] = dataframe[column].astype(float)

    return dataframe


def run_catboost_cv():

    results = []
    best_iterations = []

    for fold, (train_idx, valid_idx) in enumerate(cv.split(X_dev, y_dev_encoded), start=1):

        X_train = prepare_catboost(X_dev.iloc[train_idx])

        X_valid = prepare_catboost(X_dev.iloc[valid_idx])

        y_train = y_dev_encoded[train_idx]

        y_valid = y_dev_encoded[valid_idx]

        sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)

        model = CatBoostClassifier(
            loss_function="MultiClass",
            eval_metric="MultiClass",
            iterations=2000,
            learning_rate=0.03,
            depth=7,
            l2_leaf_reg=5,
            random_strength=0.5,
            bootstrap_type="Bayesian",
            bagging_temperature=1,
            random_seed=42,
            verbose=False,
            allow_writing_files=False,
        )

        model.fit(
            X_train,
            y_train,
            cat_features=categorical_features,
            sample_weight=sample_weight,
            eval_set=(X_valid, y_valid),
            early_stopping_rounds=100,
        )

        pred = model.predict(X_valid).flatten().astype(int)

        proba = model.predict_proba(X_valid)

        fold_metrics = calculate_metrics(y_valid, pred, proba)

        fold_metrics["fold"] = fold

        results.append(fold_metrics)

        best_iterations.append(model.get_best_iteration() + 1)

    return (pd.DataFrame(results), best_iterations)


cat_results, cat_iterations = run_catboost_cv()


# COMMAND ----------

# MAGIC %md
# MAGIC ### 6.4 Model comparison
# MAGIC

# COMMAND ----------

# Restore Python built-in round (shadowed by pyspark.sql.functions.round)

for result_df, model_name in [
    (lgbm_results, "LightGBM"),
    (xgb_results, "XGBoost"),
    (cat_results, "CatBoost"),
]:
    result_df["model"] = model_name

cv_results = pd.concat([lgbm_results, xgb_results, cat_results], ignore_index=True)

metrics = [
    "accuracy",
    "balanced_accuracy",
    "precision_macro",
    "recall_macro",
    "f1_macro",
    "f1_weighted",
    "log_loss",
    "top_2_accuracy",
    "top_3_accuracy",
]

model_comparison = cv_results.groupby("model")[metrics].agg(["mean", "std"])

model_comparison.columns = [f"{metric}_{stat}" for metric, stat in model_comparison.columns]

model_comparison = model_comparison.reset_index().sort_values("f1_macro_mean", ascending=False)

display(model_comparison)

print("Reference balanced accuracy:", round(1 / n_classes, 4))

print("Majority-class accuracy:", round(y_dev.value_counts(normalize=True).iloc[0], 4))


# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Final untouched holdout
# MAGIC
# MAGIC Cross-validation is used for model comparison.
# MAGIC LightGBM is then fitted once on the full development set and evaluated on the untouched 20% holdout.
# MAGIC LightGBM is the predeclared holdout candidate retained from the source;
# MAGIC this section does not claim it wins every possible rerun of the CV comparison.
# MAGIC
# MAGIC This is the final supervised test and should not be used for additional tuning.
# MAGIC

# COMMAND ----------

valid_lgbm_iterations = [i for i in lgbm_iterations if i is not None and i > 0]

final_n_estimators = int(np.median(valid_lgbm_iterations)) if valid_lgbm_iterations else 300

final_preprocessor = build_preprocessor()

X_dev_processed = final_preprocessor.fit_transform(X_dev)

X_test_processed = final_preprocessor.transform(X_test)

final_sample_weight = compute_sample_weight(class_weight="balanced", y=y_dev_encoded)

final_lgbm = LGBMClassifier(
    objective="multiclass",
    n_estimators=final_n_estimators,
    learning_rate=0.03,
    num_leaves=31,
    max_depth=-1,
    min_child_samples=20,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
    random_state=42,
    verbosity=-1,
)

final_lgbm.fit(X_dev_processed, y_dev_encoded, sample_weight=final_sample_weight)

test_pred = final_lgbm.predict(X_test_processed)

test_proba = final_lgbm.predict_proba(X_test_processed)

test_metrics = calculate_metrics(y_test_encoded, test_pred, test_proba)

display(pd.DataFrame([{"model": "LightGBM holdout", **test_metrics}]))

majority_class = y_dev.value_counts().idxmax()

majority_test_accuracy = y_test.eq(majority_class).mean()

print("Majority holdout accuracy:", round(majority_test_accuracy, 4))

print("Random balanced-accuracy baseline:", round(1 / n_classes, 4))


# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Robustness and alternative approaches
# MAGIC
# MAGIC The following experiments test whether the weak result is specific to one algorithm or one representation.
# MAGIC
# MAGIC They are **supporting evidence**, not separate production candidates.
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ### 8.1 Capacity / overfitting check
# MAGIC
# MAGIC If training performance is materially better than validation performance, the models have enough capacity to fit the observed data but the learned patterns do not generalize.
# MAGIC

# COMMAND ----------

X_debug = prepare_catboost(X_dev)

model_debug = CatBoostClassifier(
    iterations=500,
    depth=8,
    learning_rate=0.05,
    loss_function="MultiClass",
    random_seed=42,
    verbose=False,
    allow_writing_files=False,
)

model_debug.fit(X_debug, y_dev_encoded, cat_features=categorical_features)

train_pred = model_debug.predict(X_debug).flatten().astype(int)

print("Train accuracy:", accuracy_score(y_dev_encoded, train_pred))

print("Train F1 macro:", f1_score(y_dev_encoded, train_pred, average="macro"))


# COMMAND ----------

# MAGIC %md
# MAGIC ### 8.2 Simplified model vs. dummy baseline
# MAGIC
# MAGIC A deliberately simpler representation uses only coverage mix plus state.
# MAGIC If even this restricted formulation fails to beat the majority baseline, additional complexity is unlikely to solve the problem.
# MAGIC

# COMMAND ----------

gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=0)

tr, va = next(gss.split(X, y, groups=groups))

simple_features = [c for c in X.columns if c.startswith("coverage_share_")] + ["main_state"]

simple_model = CatBoostClassifier(
    depth=3,
    learning_rate=0.05,
    iterations=1000,
    l2_leaf_reg=10,
    loss_function="MultiClass",
    od_type="Iter",
    od_wait=50,
    verbose=0,
    random_seed=0,
    allow_writing_files=False,
)

simple_model.fit(
    X.iloc[tr][simple_features],
    y.iloc[tr],
    eval_set=(X.iloc[va][simple_features], y.iloc[va]),
    cat_features=["main_state"],
    use_best_model=True,
)

simple_pred = simple_model.predict(X.iloc[va][simple_features]).ravel()

print("Validation accuracy:", accuracy_score(y.iloc[va], simple_pred))

print("Validation F1 macro:", f1_score(y.iloc[va], simple_pred, average="macro"))

print("Majority baseline:", (y.iloc[va] == y.iloc[tr].mode()[0]).mean())


# COMMAND ----------

# MAGIC %md
# MAGIC ### 8.3 Unsupervised K-Means
# MAGIC
# MAGIC This checks whether the portfolio naturally forms feature-space clusters aligned with `industry` even without using labels.
# MAGIC
# MAGIC Adjusted Mutual Information (AMI) is compared with a permutation null.
# MAGIC

# COMMAND ----------

coverage_features = [c for c in X.columns if c.startswith("coverage_share_")]

money_features = ["total_premium", "total_sum_insured", "avg_premium", "avg_sum_insured"]

other_cluster_features = ["premium_si_ratio", "avg_policy_duration_days", "portfolio_span_days"]

Z = X[coverage_features + money_features + other_cluster_features].copy()

Z[money_features] = np.log1p(Z[money_features].clip(lower=0))

Z = pd.concat([Z, pd.get_dummies(X["main_state"], prefix="state")], axis=1)

Z = Z.replace([np.inf, -np.inf], np.nan).fillna(0)

Zs = StandardScaler().fit_transform(Z.astype(float))

y_arr = y.to_numpy()

rng = np.random.default_rng(0)
cluster_rows = []

for k in [5, 10, 15, 25]:

    cluster_labels = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(Zs)

    observed_ami = adjusted_mutual_info_score(y_arr, cluster_labels)

    null_ami = [
        adjusted_mutual_info_score(rng.permutation(y_arr), cluster_labels) for _ in range(200)
    ]

    cluster_rows.append({"k": k, "AMI": observed_ami, "null_p95": np.percentile(null_ami, 95)})

display(pd.DataFrame(cluster_rows))


# COMMAND ----------

# MAGIC %md
# MAGIC ### 8.4 One-vs-rest Logistic Regression
# MAGIC
# MAGIC The 15-class task is decomposed into 15 binary problems.
# MAGIC
# MAGIC This checks whether **any individual industry** is separable from the rest even if the full multiclass problem is difficult.
# MAGIC

# COMMAND ----------

classes = sorted(y.unique())

ovr_folds = list(
    StratifiedGroupKFold(5, shuffle=True, random_state=0).split(
        Z.to_numpy(dtype=float), y_arr, groups
    )
)

ovr_rows = []

for cls in classes:

    y_binary = (y_arr == cls).astype(int)

    oof = np.zeros(len(y_binary))

    for tr, va in ovr_folds:

        model = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))

        model.fit(Z.to_numpy(dtype=float)[tr], y_binary[tr])

        oof[va] = model.predict_proba(Z.to_numpy(dtype=float)[va])[:, 1]

    n_positive = y_binary.sum()
    n_negative = (1 - y_binary).sum()

    se_null = np.sqrt((n_positive + n_negative + 1) / (12 * n_positive * n_negative))

    threshold = 0.5 + 2.7 * se_null

    auc = roc_auc_score(y_binary, oof)

    ovr_rows.append(
        {
            "industry": cls,
            "n": n_positive,
            "auc": auc,
            "adjusted_threshold": threshold,
            "signal": auc > threshold,
        }
    )

display(pd.DataFrame(ovr_rows).sort_values("auc", ascending=False))


# COMMAND ----------

# MAGIC %md
# MAGIC ### 8.5 Policy-level model aggregated to client
# MAGIC
# MAGIC Instead of first aggregating all policies into client features, this experiment models individual policies and then averages the predicted class probabilities for each validation client.
# MAGIC
# MAGIC This tests whether policy-level granularity contains signal that was lost during client aggregation.
# MAGIC

# COMMAND ----------

df_pol = (
    df_development.filter((F.col("industry").isNotNull() & (F.col("fill_method") == "original")))
    .select(
        "ClientId",
        "coverage_type",
        "state",
        "premium",
        "sum_insured",
        "policy_duration_days",
        "industry",
    )
    .orderBy("ClientId")
    .toPandas()
)
df_pol[["premium", "sum_insured"]] = df_pol[["premium", "sum_insured"]].apply(
    pd.to_numeric, errors="raise"
)

policy_gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=0)

tr, va = next(policy_gss.split(df_pol, df_pol["industry"], groups=df_pol["ClientId"]))

policy_features = ["coverage_type", "state", "premium", "sum_insured", "policy_duration_days"]

policy_model = CatBoostClassifier(
    depth=4,
    learning_rate=0.05,
    iterations=1000,
    l2_leaf_reg=10,
    loss_function="MultiClass",
    od_type="Iter",
    od_wait=50,
    verbose=0,
    random_seed=0,
    allow_writing_files=False,
)

policy_model.fit(
    df_pol.iloc[tr][policy_features],
    df_pol.iloc[tr]["industry"],
    eval_set=(df_pol.iloc[va][policy_features], df_pol.iloc[va]["industry"]),
    cat_features=["coverage_type", "state"],
    use_best_model=True,
)

policy_proba = pd.DataFrame(
    policy_model.predict_proba(df_pol.iloc[va][policy_features]), columns=policy_model.classes_
)

policy_proba["ClientId"] = df_pol.iloc[va]["ClientId"].values

client_pred = policy_proba.groupby("ClientId").mean().idxmax(axis=1)

client_true = df_pol.iloc[va].groupby("ClientId")["industry"].first()

train_majority = df_pol.iloc[tr].groupby("ClientId")["industry"].first().mode()[0]

print("Client accuracy:", (client_pred == client_true.loc[client_pred.index]).mean())

print("Majority baseline:", (client_true == train_majority).mean())


# COMMAND ----------

# MAGIC %md
# MAGIC ### 8.6 Client-name text model
# MAGIC
# MAGIC This is the experiment most similar to a fuzzy/name-similarity approach, but it is **not traditional fuzzy matching**.
# MAGIC
# MAGIC Names are normalized and represented through:
# MAGIC - word n-grams,
# MAGIC - character n-grams,
# MAGIC - TF-IDF,
# MAGIC
# MAGIC followed by Logistic Regression.
# MAGIC
# MAGIC The cross-validation groups by normalized company name so an identical normalized name cannot appear in both train and validation.
# MAGIC

# COMMAND ----------

client_names_pd = (
    df_development.filter((F.col("industry").isNotNull() & (F.col("fill_method") == "original")))
    .select("ClientId", "client_name", "industry")
    .groupBy("ClientId", "industry")
    .agg(F.min("client_name").alias("client_name"))
    .orderBy("ClientId")
    .toPandas()
)

LEGAL_SUFFIXES = (
    r"\b("
    r"s a p i|"
    r"s de r l|"
    r"de c v|"
    r"de r l|"
    r"s a b|"
    r"s a|"
    r"s c|"
    r"c v|"
    r"r l"
    r")\b"
)


def normalize_company_name(value):

    value = unicodedata.normalize("NFKD", str(value).lower()).encode("ascii", "ignore").decode()

    value = re.sub(r"[.,]", " ", value)

    value = re.sub(LEGAL_SUFFIXES, " ", value)

    return re.sub(r"\s+", " ", value).strip()


client_names_pd["name_normalized"] = client_names_pd["client_name"].map(normalize_company_name)

print("Clients:", len(client_names_pd))

print("Unique normalized names:", client_names_pd["name_normalized"].nunique())

print(
    "Names shared by >1 ClientId:",
    (client_names_pd.groupby("name_normalized")["ClientId"].nunique() > 1).sum(),
)

X_name = client_names_pd["name_normalized"]

y_name = client_names_pd["industry"]

name_groups = client_names_pd["name_normalized"]

name_vectorizer = make_union(
    TfidfVectorizer(ngram_range=(1, 2), min_df=3),
    TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5),
)

name_model = make_pipeline(name_vectorizer, LogisticRegression(C=1.0, max_iter=2000))

name_cv = StratifiedGroupKFold(5, shuffle=True, random_state=0)

name_pred = cross_val_predict(name_model, X_name, y_name, groups=name_groups, cv=name_cv)

print("Name-model accuracy:", accuracy_score(y_name, name_pred))

print("Name-model balanced accuracy:", balanced_accuracy_score(y_name, name_pred))

print("Majority baseline:", y_name.value_counts(normalize=True).iloc[0])


# COMMAND ----------

# MAGIC %md
# MAGIC ### 8.7 Shuffled-target and positive-control checks
# MAGIC
# MAGIC Two complementary controls are used:
# MAGIC
# MAGIC - **Negative control:** shuffle `industry`. A real model should not meaningfully outperform the shuffled target.
# MAGIC - **Positive control:** inject a synthetic feature that contains controlled amounts of target signal. The same pipeline should improve when genuine signal exists.
# MAGIC
# MAGIC Together these checks help distinguish "bad implementation" from "insufficient information in the data."
# MAGIC

# COMMAND ----------

coverage_only = [c for c in X.columns if c.startswith("coverage_share_")]

control_features = coverage_only + ["main_state"]

control_groups = model_pd["ClientId"].to_numpy()


def run_control_pipeline(X_control, y_control, categorical, seed=0):

    tr, va = next(
        GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed).split(
            X_control, y_control, groups=control_groups
        )
    )

    model = CatBoostClassifier(
        depth=3,
        learning_rate=0.05,
        iterations=1000,
        l2_leaf_reg=10,
        loss_function="MultiClass",
        od_type="Iter",
        od_wait=50,
        verbose=0,
        random_seed=seed,
        allow_writing_files=False,
    )

    model.fit(
        X_control.iloc[tr],
        y_control.iloc[tr],
        eval_set=(X_control.iloc[va], y_control.iloc[va]),
        cat_features=list(categorical),
        use_best_model=True,
    )

    pred = model.predict(X_control.iloc[va]).ravel()

    return {
        "accuracy": accuracy_score(y_control.iloc[va], pred),
        "balanced_accuracy": balanced_accuracy_score(y_control.iloc[va], pred),
        "majority_baseline": (y_control.iloc[va] == y_control.iloc[tr].mode()[0]).mean(),
    }


real_control = run_control_pipeline(X[control_features], y, ["main_state"])

rng = np.random.default_rng(0)

y_shuffled = pd.Series(rng.permutation(y.to_numpy()), index=y.index)

shuffled_control = run_control_pipeline(X[control_features], y_shuffled, ["main_state"])

print("Real target:", real_control)

print("Shuffled target:", shuffled_control)


classes_array = np.array(sorted(y.unique()))

for signal_rate in [0.05, 0.10, 0.20]:

    synthetic_hint = np.where(
        rng.random(len(y)) < signal_rate, y.to_numpy(), rng.choice(classes_array, len(y))
    )

    X_positive = X[control_features].copy()

    X_positive["synthetic_signal"] = synthetic_hint

    positive_result = run_control_pipeline(X_positive, y, ["main_state", "synthetic_signal"])

    print(f"Positive control " f"{signal_rate:.0%}:", positive_result)


# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Decision criteria (rerun before asserting results)
# MAGIC
# MAGIC The defensible conclusion is **not** that machine learning is mathematically impossible.
# MAGIC
# MAGIC The candidate's historical conclusion was (not recomputed during code packaging):
# MAGIC
# MAGIC > **With the variables available in this portfolio, there is no evidence of sufficient out-of-sample predictive signal to reliably infer `industry` for previously unseen clients.**
# MAGIC
# MAGIC The decision is based on the combined evidence:
# MAGIC
# MAGIC - weak pre-model associations,
# MAGIC - multiclass performance close to naive/random baselines,
# MAGIC - a holdout comparison (historical results must be rerun with this corrected split),
# MAGIC - no useful natural clustering by industry,
# MAGIC - no individual industry with convincing one-vs-rest separability,
# MAGIC - no material gain from policy-level modeling,
# MAGIC - no generalizable signal from company-name morphology,
# MAGIC - negative-control results similar to real-target results,
# MAGIC - and a positive control showing that the pipeline does improve when predictive signal is deliberately introduced.
# MAGIC
# MAGIC Therefore, **ML predictions should not be used for automatic industry imputation** in the final fill strategy.
# MAGIC
# MAGIC This conclusion applies to the current data and features. It does not imply that the problem would remain unlearnable if stronger external variables were available, such as verified economic activity, NAICS/SIC codes, broker/underwriter metadata, or authoritative company enrichment.
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Appendix — Deterministic ClientId validation
# MAGIC
# MAGIC This is not an ML experiment. It validates the higher-confidence deterministic imputation rule used earlier in the pipeline.
# MAGIC

# COMMAND ----------

client_consistency = (
    df_ml.filter((F.col("industry").isNotNull() & (F.col("fill_method") == "original")))
    .groupBy("ClientId")
    .agg(F.countDistinct("industry").alias("n_industries"))
)

conflicting_clients = client_consistency.filter(F.col("n_industries") > 1).count()

print("Clients with conflicting " "original industries:", conflicting_clients)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Save reproducible research outputs
# MAGIC These are produced only after running the reviewed notebook on original input.
# MAGIC They are distinct from historical scores in the submission reports.

# COMMAND ----------

import importlib.metadata
from src.data_processing.runtime import write_json

MODELING_OUTPUT.mkdir(parents=True)
cv_results.to_csv(MODELING_OUTPUT / "cv_folds.csv", index=False)
model_comparison.to_csv(MODELING_OUTPUT / "model_comparison.csv", index=False)
pd.DataFrame(
    {
        "ClientId": all_model_client_ids,
        "split": [
            "development" if idx in X_dev.index else "holdout" for idx in all_model_client_ids.index
        ],
    }
).to_csv(MODELING_OUTPUT / "client_split.csv", index=False)
write_json(
    MODELING_OUTPUT / "holdout.json",
    {
        "model": "predeclared LightGBM",
        "seed": 42,
        "development_clients": len(X_dev),
        "holdout_clients": len(X_test),
        "metrics": {key: float(value) for key, value in test_metrics.items()},
        "majority_accuracy": float(majority_test_accuracy),
        "ml_used_for_imputation": False,
        "package_versions": {
            name: importlib.metadata.version(name)
            for name in (
                "numpy",
                "pandas",
                "scipy",
                "scikit-learn",
                "lightgbm",
                "xgboost",
                "catboost",
            )
        },
    },
)
