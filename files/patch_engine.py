import os

# Get absolute path to the engine_core file
current_dir = os.path.dirname(os.path.abspath(__file__))
target_file = os.path.join(current_dir, "engine_core.py")

# The exact text of your working class
correct_code = """import numpy as np
from sklearn.decomposition import PCA
from sklearn.covariance import LedoitWolf
from scipy.stats import chi2

class EngineCore:
    def __init__(self, max_pca_dims=50, mad_threshold=3.0, p_value_threshold=0.05):
        self.max_pca_dims = max_pca_dims
        self.mad_threshold = mad_threshold
        self.p_value_threshold = p_value_threshold

    def mad_filter(self, corpus_matrix):
        n_samples = corpus_matrix.shape[0]
        if n_samples < 5:
            return corpus_matrix
            
        centroid = np.median(corpus_matrix, axis=0)
        distances = np.linalg.norm(corpus_matrix - centroid, axis=1)
        
        median_dist = np.median(distances)
        mad = np.median(np.abs(distances - median_dist))
        
        if mad == 0:
            mad = 1e-6 
            
        modified_z_scores = 0.6745 * (distances - median_dist) / mad
        clean_indices = np.abs(modified_z_scores) < self.mad_threshold
        
        clean_corpus = corpus_matrix[clean_indices]
        print(f"MAD Filter: Removed {n_samples - len(clean_corpus)} garbage images.")
        return clean_corpus

    def execute_pipeline(self, query_vector, raw_corpus_matrix):
        if np.isnan(query_vector).any() or np.isnan(raw_corpus_matrix).any():
            return {"status": "error", "message": "NaN values detected in embeddings."}

        clean_corpus = self.mad_filter(raw_corpus_matrix)
        n_samples = clean_corpus.shape[0]

        if n_samples < 3:
            return {"status": "error", "message": f"Only {n_samples} valid reference images survived filtering. Cannot compute variance."}

        target_dims = min(n_samples - 1, self.max_pca_dims)
        pca = PCA(n_components=target_dims)
        
        try:
            corpus_reduced = pca.fit_transform(clean_corpus)
            query_reduced = pca.transform(query_vector.reshape(1, -1))[0]
        except Exception as e:
            return {"status": "error", "message": f"PCA projection failed: {e}"}

        try:
            lw = LedoitWolf().fit(corpus_reduced)
            cov_inv = np.linalg.inv(lw.covariance_)
            mean_ref = np.mean(corpus_reduced, axis=0)
            
            delta = query_reduced - mean_ref
            mahalanobis_sq = np.dot(np.dot(delta, cov_inv), delta.T)
            mahalanobis_dist = np.sqrt(max(0.0, mahalanobis_sq))
            
        except Exception as e:
             return {"status": "error", "message": f"Covariance estimation failed: {e}"}

        degrees_of_freedom = target_dims
        p_value = 1.0 - chi2.cdf(mahalanobis_sq, degrees_of_freedom)
        is_anomaly = p_value < self.p_value_threshold

        return {
            "status": "success",
            "is_anomaly": is_anomaly,
            "p_value": float(p_value),
            "mahalanobis_distance": float(mahalanobis_dist),
            "pca_dimensions_used": target_dims,
            "images_used": n_samples
        }
"""

# Force overwrite the file programmatically at the OS level
print(f"Overwriting filesystem block at: {target_file}")
with open(target_file, "w", encoding="utf-8") as f:
    f.write(correct_code)

print("✅ File successfully flushed to disk layout.")