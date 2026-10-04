"""Small dependency-free diagnostics used in the research notebook."""

from collections import defaultdict
from math import isfinite, sqrt


def correlation_ratio(categories, values):
    """Return eta for a categorical target and numeric predictor.

    The original notebook called this function without defining it. Eta measures
    between-category variation, not predictive accuracy or a causal relationship.
    Constant/empty finite observations return zero rather than dividing by zero.
    """
    if len(categories) != len(values):
        raise ValueError("categories and values must have equal lengths")
    groups = defaultdict(list)
    for category, value in zip(categories, values):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if category is not None and isfinite(numeric):
            groups[str(category)].append(numeric)
    observed = [value for group in groups.values() for value in group]
    if not observed:
        return 0.0
    mean = sum(observed) / len(observed)
    total = sum((value - mean) ** 2 for value in observed)
    if not total:
        return 0.0
    between = sum(len(group) * (sum(group) / len(group) - mean) ** 2 for group in groups.values())
    return sqrt(min(1.0, max(0.0, between / total)))
