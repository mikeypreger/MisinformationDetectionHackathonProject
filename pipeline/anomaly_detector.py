"""
anomaly_detector.py  —  integrated

Replaces the original chi-square Mahalanobis stub with EngineCore, which adds:
  - Cosine-distance MAD filter (robust to scraper garbage)
  - Ledoit-Wolf shrinkage covariance
  - Hotelling T² F-distribution (finite-sample correction)
  - GMM pipeline for multi-angle / multi-cluster corpora

Public API is unchanged: run_anomaly_detection(context_embeddings, query_embedding)
returns the same dict shape MyApp.py already reads.
"""

import numpy as np
from engine_core import EngineCore

# One shared instance — constructor is cheap, no model weights
_engine = EngineCore(
    variance_target=0.95,
    base_mad_threshold=3.0,
    p_value_threshold=0.05,
)


def run_anomaly_detection(
    context_embeddings: np.ndarray,
    query_embedding: np.ndarray,
    anomaly_threshold: float = 0.05,
    use_gmm: bool = False,
) -> dict:
    """
    Full engine: MAD filter → PCA subspace → Ledoit-Wolf Mahalanobis →
    Hotelling T² p-value  (or GMM empirical p-value when use_gmm=True).

    Args:
        context_embeddings : (n, D) float32  — L2-normalised embeddings of context images
        query_embedding    : (D,)   float32  — embedding of the post image
        anomaly_threshold  : p-value below which the image is flagged as an anomaly
        use_gmm            : set True when the context corpus is known to be multi-cluster
                             (e.g. building shots from multiple angles). GMM selects the
                             number of Gaussian components via BIC and computes an
                             empirical p-value that is robust to bimodal/multimodal corpora.

    Returns dict with the same keys MyApp.py already reads, plus extras from EngineCore.
    """
    n_original = len(context_embeddings)

    if n_original < 10:
        return {
            "error": f"Too few context images ({n_original}) for statistical analysis",
            "is_anomaly": None,
        }

    # Override the engine's stored threshold with whatever the caller passes
    _engine.p_value_threshold = anomaly_threshold

    if use_gmm:
        raw = _engine.execute_gmm_pipeline(query_embedding, context_embeddings)
    else:
        raw = _engine.execute_pipeline(query_embedding, context_embeddings)

    # ── Normalise the two different result shapes into one flat dict ──────────
    if raw.get("status") == "error":
        return {
            "error": raw.get("message", "EngineCore error"),
            "is_anomaly": None,
        }

    if use_gmm:
        # GMM result shape:
        # { status, is_anomaly, metrics:{p_value, gmm_query_log_likelihood},
        #   diagnostics:{gmm_components_used, pca_dimensions_used,
        #                images_used, images_filtered} }
        diag = raw.get("diagnostics", {})
        metrics = raw.get("metrics", {})
        return {
            "is_anomaly"              : raw["is_anomaly"],
            "p_value"                 : round(metrics.get("p_value", 0.0), 6),
            "mahalanobis_distance"    : None,   # not computed in GMM mode
            "pca_components_used"     : diag.get("pca_dimensions_used"),
            "outliers_removed_by_mad" : diag.get("images_filtered", 0),
            "anomaly_threshold"       : anomaly_threshold,
            # bonus keys (ignored by MyApp.py but useful for the expander)
            "gmm_components_used"     : diag.get("gmm_components_used"),
            "gmm_log_likelihood"      : metrics.get("gmm_query_log_likelihood"),
            "images_used"             : diag.get("images_used"),
        }
    else:
        # Single-Gaussian result shape:
        # { status, is_anomaly, p_value, mahalanobis_distance,
        #   pca_dimensions_used, images_used }
        n_used    = raw.get("images_used", n_original)
        n_removed = n_original - n_used
        return {
            "is_anomaly"              : raw["is_anomaly"],
            "p_value"                 : round(raw.get("p_value", 0.0), 6),
            "mahalanobis_distance"    : round(raw.get("mahalanobis_distance", 0.0), 4),
            "pca_components_used"     : raw.get("pca_dimensions_used"),
            "outliers_removed_by_mad" : n_removed,
            "anomaly_threshold"       : anomaly_threshold,
        }