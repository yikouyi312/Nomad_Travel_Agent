"""
Statistical helpers for benchmark evaluation.

Provides bootstrap confidence intervals and effect-size measures
that do not depend on normality assumptions — suitable for small n.
"""

import math
import random
from typing import Dict, List


def bootstrap_ci(scores: List[float], n_bootstrap: int = 1000, ci: float = 0.95) -> Dict[str, float]:
    """
    Compute bootstrap confidence interval for the mean of scores.

    Args:
        scores: List of metric values (e.g. overall_score per task).
        n_bootstrap: Number of bootstrap resamples (default 1000).
        ci: Confidence level (default 0.95 → 95% CI).

    Returns:
        {"mean": float, "ci_lower": float, "ci_upper": float, "std": float}
    """
    if not scores:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "std": 0.0}

    n = len(scores)
    rng = random.Random(42)  # Fixed seed for reproducibility
    boot_means = []
    for _ in range(n_bootstrap):
        sample = [scores[rng.randint(0, n - 1)] for _ in range(n)]
        boot_means.append(sum(sample) / n)

    boot_means.sort()
    alpha = 1 - ci
    lo_idx = int(math.floor((alpha / 2) * n_bootstrap))
    hi_idx = int(math.ceil((1 - alpha / 2) * n_bootstrap)) - 1
    lo_idx = max(0, min(lo_idx, n_bootstrap - 1))
    hi_idx = max(0, min(hi_idx, n_bootstrap - 1))

    mean_val = sum(scores) / n
    std_val = (sum((s - mean_val) ** 2 for s in scores) / n) ** 0.5

    return {
        "mean": round(mean_val, 4),
        "ci_lower": round(boot_means[lo_idx], 4),
        "ci_upper": round(boot_means[hi_idx], 4),
        "std": round(std_val, 4),
    }


def cohens_d(group1: List[float], group2: List[float]) -> float:
    """
    Compute Cohen's d effect size between two groups.

    Uses pooled standard deviation. Returns 0 if either group is empty
    or both have zero variance.
    """
    if not group1 or not group2:
        return 0.0

    m1, m2 = sum(group1) / len(group1), sum(group2) / len(group2)
    var1 = sum((x - m1) ** 2 for x in group1) / max(len(group1) - 1, 1)
    var2 = sum((x - m2) ** 2 for x in group2) / max(len(group2) - 1, 1)

    pooled_std = math.sqrt((var1 + var2) / 2)
    if pooled_std == 0:
        return 0.0
    return round((m1 - m2) / pooled_std, 4)
