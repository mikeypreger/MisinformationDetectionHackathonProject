import numpy as np
from scipy.stats import median_abs_deviation, chi2
from sklearn.decomposition import PCA
from sklearn.covariance import LedoitWolf


def _mad_filter(embeddings: np.ndarray, threshold: float = 3.0) -> tuple[np.ndarray, int]:
    """
    Remove embedding rows that are outliers by L2-norm MAD score.
    Returns (filtered_embeddings, n_removed).
    """
    norms = np.linalg.norm(embeddings, axis=1)
    median = np.median(norms)
    mad = median_abs_deviation(norms, scale="normal")
    if mad == 0:
        return embeddings, 0
    z_scores = np.abs(norms - median) / mad
    mask = z_scores <= threshold
    n_removed = int((~mask).sum())
    return embeddings[mask], n_removed


def _fit_pca(embeddings: np.ndarray, variance_threshold: float = 0.95) -> tuple[PCA, np.ndarray]:
    """
    Fit PCA retaining components that explain variance_threshold of total variance.
    Guards against n_components >= n_samples.
    Returns (fitted_pca, projected_embeddings).
    """
    n_samples = len(embeddings)
    # PCA n_components as float means "fraction of variance"
    # But we also can't have more components than min(n_samples-1, n_features)
    max_components = min(n_samples - 1, embeddings.shape[1])
    if max_components < 2:
        raise ValueError(f"Too few samples ({n_samples}) for PCA")

    pca = PCA(n_components=variance_threshold, svd_solver="full")
    projected = pca.fit_transform(embeddings)

    # If PCA chose more components than max_components allows, re-fit with hard cap
    if projected.shape[1] >= n_samples:
        n_cap = max(1, n_samples - 1)
        pca = PCA(n_components=n_cap, svd_solver="full")
        projected = pca.fit_transform(embeddings)

    return pca, projected


def _mahalanobis_distance(projected_context: np.ndarray, query_projected: np.ndarray) -> float:
    """
    Compute Mahalanobis distance of query_projected from the context cluster center
    using a Ledoit-Wolf regularized covariance estimator.
    Returns the distance (not squared).
    """
    lw = LedoitWolf()
    lw.fit(projected_context)
    center = np.mean(projected_context, axis=0)
    diff = query_projected - center
    precision = lw.get_precision()
    d_sq = float(diff @ precision @ diff)
    return float(np.sqrt(max(d_sq, 0.0)))


def run_anomaly_detection(
    context_embeddings: np.ndarray,
    query_embedding: np.ndarray,
    anomaly_threshold: float = 0.05,
) -> dict:
    """
    Full engine core: MAD filter → PCA subspace → Ledoit-Wolf Mahalanobis → chi2 p-value.

    Args:
        context_embeddings: shape (n, 512), L2-normalized CLIP embeddings of context images
        query_embedding:    shape (512,), L2-normalized CLIP embedding of the post image
        anomaly_threshold:  p-value below which the image is considered an anomaly

    Returns dict with anomaly stats, or dict with "error" key if data is insufficient.
    """
    n_original = len(context_embeddings)

    if n_original < 10:
        return {
            "error": f"Too few context images embedded ({n_original}) for statistical analysis",
            "is_anomaly": None,
        }

    # Step 1: MAD filter
    filtered, n_removed = _mad_filter(context_embeddings)
    if len(filtered) < 10:
        return {
            "error": f"MAD filter left too few samples ({len(filtered)}); cannot proceed",
            "is_anomaly": None,
            "outliers_removed_by_mad": n_removed,
        }

    # Step 2: PCA subspace
    try:
        pca, projected_context = _fit_pca(filtered)
    except ValueError as e:
        return {"error": str(e), "is_anomaly": None, "outliers_removed_by_mad": n_removed}

    n_components = projected_context.shape[1]

    # Project query into the same PCA subspace
    query_projected = pca.transform(query_embedding.reshape(1, -1))[0]

    # Step 3: Ledoit-Wolf Mahalanobis distance
    try:
        mahal = _mahalanobis_distance(projected_context, query_projected)
    except Exception as e:
        return {
            "error": f"Mahalanobis computation failed: {e}",
            "is_anomaly": None,
            "outliers_removed_by_mad": n_removed,
            "pca_components_used": n_components,
        }

    # Step 4: chi2 p-value (Mahalanobis² ~ chi2(df=n_components))
    p_value = float(chi2.sf(mahal ** 2, df=n_components))
    is_anomaly = p_value < anomaly_threshold

    return {
        "outliers_removed_by_mad": n_removed,
        "pca_components_used": n_components,
        "mahalanobis_distance": round(mahal, 4),
        "p_value": round(p_value, 6),
        "is_anomaly": is_anomaly,
        "anomaly_threshold": anomaly_threshold,
    }
