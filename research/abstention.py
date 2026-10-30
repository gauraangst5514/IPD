"""Finite-sample upper-tail calibration for fixed-gallery unknown query groups."""
import math
import numpy as np


def upper_tail_threshold(scores, alpha):
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 1 or not len(scores) or not np.isfinite(scores).all():
        raise ValueError('Provide nonempty finite calibration group scores')
    if not 0 < alpha < 1:
        raise ValueError('alpha must be between zero and one')
    rank = math.ceil((len(scores) + 1) * (1 - alpha))
    return float(np.sort(scores)[rank - 1]) if rank <= len(scores) else math.inf


def binomial_upper(errors, groups, confidence=.95):
    from scipy.stats import beta
    if not 0 <= errors <= groups or groups < 1:
        raise ValueError('Invalid error/group counts')
    return 1. if errors == groups else float(beta.ppf(confidence, errors + 1, groups - errors))
