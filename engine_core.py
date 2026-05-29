import numpy as np
from sklearn.decomposition import PCA
from sklearn.covariance import LedoitWolf
from sklearn.mixture import GaussianMixture
from scipy.stats import chi2, f as f_dist

class EngineCore:
    def __init__(self, variance_target=0.95, base_mad_threshold=3.0, p_value_threshold=0.01):
        self.variance_target = variance_target
        self.base_mad_threshold = base_mad_threshold
        self.p_value_threshold = p_value_threshold

    def mad_filter(self, corpus_matrix):
        """Removes scraped garbage arrays using high-dimensional Cosine Distance."""
        n_samples = corpus_matrix.shape[0]
        if n_samples < 5:
            return corpus_matrix # Not enough data to reliably find a median

        # --- UPGRADE 1: Cosine Distance MAD Filtering ---
        # Normalize vectors to unit length to calculate angles instead of magnitudes
        norms = np.linalg.norm(corpus_matrix, axis=1, keepdims=True)
        # Handle zero-vector edge cases safely
        norms[norms == 0] = 1e-6
        normalized_corpus = corpus_matrix / norms

        # Find the directional spatial median (the true center concept)
        median_vector = np.median(normalized_corpus, axis=0)
        median_norm = np.linalg.norm(median_vector)
        if median_norm == 0: median_norm = 1e-6
        median_vector /= median_norm

        # Calculate Cosine Distance (1.0 - Cosine Similarity) for each image
        cosine_distances = 1.0 - np.dot(normalized_corpus, median_vector)

        # Calculate Median Absolute Deviation (MAD) on the angles
        median_dist = np.median(cosine_distances)
        mad = np.median(np.abs(cosine_distances - median_dist))
        if mad == 0: mad = 1e-6

        # --- UPGRADE 2: Dynamic Sample Scaling ---
        # Tighten the filter slightly for small samples to catch hidden outliers
        dynamic_threshold = self.base_mad_threshold
        if n_samples < 20:
            dynamic_threshold = self.base_mad_threshold * 0.85

        modified_z_scores = 0.6745 * (cosine_distances - median_dist) / mad
        clean_indices = np.abs(modified_z_scores) < dynamic_threshold

        clean_corpus = corpus_matrix[clean_indices]
        print(f"MAD Filter: Removed {n_samples - len(clean_corpus)} garbage images from baseline.")
        return clean_corpus

    def _run_pca_reduction(self, clean_corpus, query_vector):
        """
        Shared PCA reduction used by both execute_pipeline and execute_gmm_pipeline.
        Returns (corpus_reduced, query_reduced, target_dims).
        whiten=False so LedoitWolf receives a corpus with non-uniform component variances,
        allowing it to actually shrink toward a useful prior instead of a near-identity matrix.
        """
        n_samples = clean_corpus.shape[0]
        max_possible_dims = n_samples - 2

        # First pass: discover how many dims capture variance_target of the layout
        pca_finder = PCA(n_components=min(max_possible_dims, 50))
        pca_finder.fit(clean_corpus)
        cumulative_variance = np.cumsum(pca_finder.explained_variance_ratio_)

        under_target = np.where(cumulative_variance < self.variance_target)[0]
        target_dims = len(under_target) + 1 if len(under_target) > 0 else 2
        target_dims = min(target_dims, max_possible_dims)

        # FIX: whiten=False — whitening forces corpus covariance → I, making LedoitWolf
        # compute Mahalanobis ≈ Euclidean. Without whitening, LW properly shrinks the
        # empirical covariance (which has non-uniform eigenvalues) toward a scaled identity.
        pca = PCA(n_components=target_dims, whiten=False)
        corpus_reduced = pca.fit_transform(clean_corpus)
        query_reduced = pca.transform(query_vector.reshape(1, -1))[0]

        return corpus_reduced, query_reduced, target_dims

    def execute_pipeline(self, query_vector, raw_corpus_matrix):
        """Runs the upgraded 4-stage statistical anomaly check."""
        if np.isnan(query_vector).any() or np.isnan(raw_corpus_matrix).any():
            return {"status": "error", "message": "NaN values detected in embeddings."}

        # Stage 1: Filter out the scraping mistakes
        clean_corpus = self.mad_filter(raw_corpus_matrix)
        n_samples = clean_corpus.shape[0]

        if n_samples < 5:
            return {"status": "error", "message": f"Only {n_samples} images passed filtering. Cannot compute variance."}

        # Stage 2: PCA Subspace Optimization (whiten=False, see _run_pca_reduction)
        try:
            corpus_reduced, query_reduced, target_dims = self._run_pca_reduction(clean_corpus, query_vector)
        except Exception as e:
            return {"status": "error", "message": f"Subspace optimization failed: {e}"}

        # Stage 3: Ledoit-Wolf Shrinkage
        try:
            lw = LedoitWolf().fit(corpus_reduced)
            cov_inv = np.linalg.inv(lw.covariance_)
            mean_ref = np.mean(corpus_reduced, axis=0)

            delta = query_reduced - mean_ref
            mahalanobis_sq = np.dot(np.dot(delta, cov_inv), delta.T)
            mahalanobis_dist = np.sqrt(max(0.0, mahalanobis_sq))
        except Exception as e:
             return {"status": "error", "message": f"Covariance structural calculation failed: {e}"}

        # Stage 4: Hotelling T² exact F-distribution
        # Replaces the asymptotic chi-square approximation (valid only as N→∞).
        # Uses the prediction interval formula for a single new observation vs N training samples.
        # See Johnson & Wichern "Applied Multivariate Statistical Analysis" eq. 5-29.
        # Guard: F(p, n-p) requires n-p ≥ 5 for finite variance; below that the test has near-zero
        # power (F distribution degenerates), so we fall back to chi-square.
        n, p = n_samples, target_dims
        if n > p and (n - p) >= 5:
            f_stat = (n * (n - p)) / (p * (n - 1) * (n + 1)) * mahalanobis_sq
            p_value = 1.0 - f_dist.cdf(f_stat, dfn=p, dfd=n - p)
        else:
            # Fallback: chi-square when N ≤ p or residual df < 5
            p_value = 1.0 - chi2.cdf(mahalanobis_sq, p)

        is_anomaly = p_value < self.p_value_threshold

        return {
            "status": "success",
            "is_anomaly": is_anomaly,
            "p_value": float(p_value),
            "mahalanobis_distance": float(mahalanobis_dist),
            "pca_dimensions_used": int(target_dims),
            "images_used": int(n_samples)
        }

    def _fit_gmm_bic(self, data, max_k=5):
        """
        Fits a Gaussian Mixture Model, selecting the number of components via BIC.
        Enforces at least 10 data points per component to prevent degeneracy.
        """
        max_k_allowed = max(1, min(max_k, len(data) // 10))
        best_bic, best_gmm = np.inf, None
        for k in range(1, max_k_allowed + 1):
            gmm = GaussianMixture(
                n_components=k,
                covariance_type='diag',  # 'full' is rank-deficient when n/k < p
                reg_covar=1e-6,
                max_iter=200,
                random_state=42
            )
            gmm.fit(data)
            bic = gmm.bic(data)
            if bic < best_bic:
                best_bic, best_gmm = bic, gmm
        return best_gmm

    def execute_gmm_pipeline(self, query_vector, raw_corpus_matrix, max_gmm_components=5):
        """
        GMM alternative to execute_pipeline for multi-angle building corpora.

        Problem solved: when the reference corpus has shots from multiple angles
        (front, side, aerial), the single-Gaussian Mahalanobis model inflates its
        covariance ellipsoid to cover all clusters. This creates a large false-negative
        zone — anomalies from different buildings can fall inside the inflated ellipsoid.

        Solution: fit a GMM with BIC-selected components. Each angle cluster gets its own
        tight Gaussian. A query must fit into at least one component to pass.

        p-value is empirical: the fraction of corpus members whose GMM log-likelihood
        is <= the query's log-likelihood. This is distribution-free and always well-calibrated,
        avoiding the need to derive the asymptotic distribution of the GMM log-likelihood ratio.
        """
        if np.isnan(query_vector).any() or np.isnan(raw_corpus_matrix).any():
            return {"status": "error", "message": "NaN values detected in embeddings."}

        clean_corpus = self.mad_filter(raw_corpus_matrix)
        n_samples = clean_corpus.shape[0]

        if n_samples < 10:
            return {"status": "error", "message": f"Only {n_samples} images passed filtering. GMM requires at least 10."}

        try:
            corpus_reduced, query_reduced, target_dims = self._run_pca_reduction(clean_corpus, query_vector)
        except Exception as e:
            return {"status": "error", "message": f"Subspace optimization failed: {e}"}

        try:
            # Crop to top dims before GMM — the noise PCA dims overwhelm BIC in high-dimensional
            # space, causing it to prefer k=1. Keeping only sqrt(n_samples) top dims ensures
            # the cluster signal dominates model-complexity penalty.
            gmm_dims = max(3, min(target_dims, int(np.sqrt(n_samples))))
            corpus_gmm = corpus_reduced[:, :gmm_dims]
            query_gmm = query_reduced[:gmm_dims].reshape(1, -1)

            gmm = self._fit_gmm_bic(corpus_gmm, max_k=max_gmm_components)
            corpus_scores = gmm.score_samples(corpus_gmm)
            query_score = float(gmm.score_samples(query_gmm)[0])
            # Empirical p-value: fraction of corpus members at or below the query's likelihood
            p_value = float(np.mean(corpus_scores <= query_score))
            n_components_used = int(gmm.n_components)
        except Exception as e:
            return {"status": "error", "message": f"GMM fitting failed: {e}"}

        is_anomaly = p_value < self.p_value_threshold

        return {
            "status": "success",
            "is_anomaly": is_anomaly,
            "metrics": {
                "p_value": float(p_value),
                "gmm_query_log_likelihood": float(query_score)
            },
            "diagnostics": {
                "gmm_components_used": n_components_used,
                "pca_dimensions_used": int(target_dims),
                "images_used": int(n_samples),
                "images_filtered": int(raw_corpus_matrix.shape[0] - n_samples)
            }
        }