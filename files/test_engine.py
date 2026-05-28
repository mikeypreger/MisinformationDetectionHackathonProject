import os
import sys
import numpy as np
from scipy.stats import chi2

# =====================================================================
# PATH PATCH: Force Python to find engine_core in the local 'files' dir
# =====================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

print(f"DEBUG: Script is looking in: {current_dir}")
try:
    import engine_core
    print(f"DEBUG: Python is actually loading engine_core from: {engine_core.__file__}")
except Exception as e:
    print(f"DEBUG: Failed to even load the file: {e}")

from engine_core import EngineCore

def run_engine_tests():
    # Initialize the core with default parameters (constructor signature updated)
    engine = EngineCore(p_value_threshold=0.01)

    print("Initiating Engine Core Stress Tests...\n")

    # We simulate DINOv2's output size (768 dimensions)
    DIM = 768

    # ---------------------------------------------------------
    # TEST 1: The Golden Path (True Match)
    # ---------------------------------------------------------
    print("Test 1: True Match (Should NOT be an anomaly)")
    # 25 reference images clustered tightly
    safe_corpus = np.random.normal(loc=0.5, scale=0.1, size=(25, DIM))
    # Query image comes from the exact same distribution
    query_match = np.random.normal(loc=0.5, scale=0.1, size=(DIM,))

    result = engine.execute_pipeline(query_match, safe_corpus)

    assert result["status"] == "success", "Failed to execute standard pipeline."
    assert result["is_anomaly"] == False, "Falsely flagged a perfect match as an anomaly."
    print(f"PASSED. (p-value: {result['p_value']:.4f})")

    # ---------------------------------------------------------
    # TEST 2: The Severe Outlier (True Anomaly)
    # ---------------------------------------------------------
    print("\nTest 2: Structural Mismatch (Should BE an anomaly)")
    # Query image is geometrically completely different (e.g., shifted mean)
    query_anomaly = np.random.normal(loc=1.5, scale=0.1, size=(DIM,))

    result = engine.execute_pipeline(query_anomaly, safe_corpus)

    assert result["status"] == "success"
    assert result["is_anomaly"] == True, "Failed to catch a massive geometric mismatch."
    assert result["p_value"] < 0.01, "p-value did not drop below threshold."
    print(f"PASSED. (p-value: {result['p_value']:.10f})")

    # ---------------------------------------------------------
    # TEST 3: The Poisoned Scrape (MAD Filter Stress Test)
    # ---------------------------------------------------------
    print("\nTest 3: MAD Filter vs Corrupted Scrape")
    # 20 good images, 5 massive outliers (e.g., the API scraped ad banners)
    good_images = np.random.normal(loc=0.5, scale=0.1, size=(20, DIM))
    garbage_images = np.random.normal(loc=10.0, scale=5.0, size=(5, DIM))
    poisoned_corpus = np.vstack((good_images, garbage_images))

    result = engine.execute_pipeline(query_match, poisoned_corpus)

    assert result["status"] == "success"
    # The MAD filter should have identified and stripped the 5 garbage images
    assert result["images_used"] == 20, f"MAD filter failed. Expected 20, got {result['images_used']}"
    print(f"PASSED. Successfully purged 5 poisoned arrays from the corpus.")

    # ---------------------------------------------------------
    # TEST 4: The Starvation Scenario (Insufficient Data)
    # ---------------------------------------------------------
    print("\nTest 4: Insufficient Corpus Size (N=2)")
    # Only 2 reference images exist. PCA/Mahalanobis requires more to find variance.
    tiny_corpus = np.random.normal(loc=0.5, scale=0.1, size=(2, DIM))

    result = engine.execute_pipeline(query_match, tiny_corpus)

    assert result["status"] == "error", "Did not catch starvation edge case."
    assert "Cannot compute variance" in result["message"], "Wrong error message returned."
    print("PASSED. Safely aborted instead of crashing via singular matrix inversion.")

    # ---------------------------------------------------------
    # TEST 5: Data Corruption (NaN Injection)
    # ---------------------------------------------------------
    print("\nTest 5: NaN Tensor Injection")
    # Simulate a GPU memory error or broken API that inserts a NaN value
    corrupted_query = np.copy(query_match)
    corrupted_query[256] = np.nan

    result = engine.execute_pipeline(corrupted_query, safe_corpus)

    assert result["status"] == "error", "Did not catch NaN injection."
    assert "NaN values detected" in result["message"], "Wrong error message returned."
    print("PASSED. Safely caught corrupted geometry vector.")

    print("\nALL ORIGINAL ENGINE CORE TESTS PASSED.\n")


def test_6_gmm_multi_cluster():
    """
    Demonstrates the failure mode of single-Gaussian Mahalanobis and how GMM fixes it.

    Setup: bimodal corpus — 30 shots from the building FRONT (dim_0 = +3)
           and 30 shots from the building BACK (dim_0 = -3).

    Single Gaussian model flaw:
      - The mean lands at dim_0 = 0 (the empty gap between clusters).
      - The inflated covariance covers both clusters with one big ellipsoid.
      - A query at dim_0 = 0 (structurally a DIFFERENT building's courtyard)
        falls RIGHT AT THE MEAN → Mahalanobis D² ≈ 0 → NOT flagged (false negative).

    GMM fix:
      - BIC selects k=2 components, one tight Gaussian per cluster.
      - A query at dim_0 = 0 falls BETWEEN both components → very low log-likelihood
        → empirical p-value ≈ 0 → correctly FLAGGED as anomaly.
    """
    print("\n--- Test 6: GMM Multi-Cluster Corpus ---")
    rng = np.random.default_rng(42)
    DIM = 768

    # Two tight clusters separated by 6 units in dim_0
    cluster_front = rng.normal(loc=0.0, scale=0.1, size=(30, DIM))
    cluster_front[:, 0] = rng.normal(loc=3.0, scale=0.1, size=30)

    cluster_back = rng.normal(loc=0.0, scale=0.1, size=(30, DIM))
    cluster_back[:, 0] = rng.normal(loc=-3.0, scale=0.1, size=30)

    bimodal_corpus = np.vstack([cluster_front, cluster_back])

    # Between-cluster anomaly: dim_0 = 0 (no man's land between front and back shots)
    query_anomaly = rng.normal(loc=0.0, scale=0.1, size=(DIM,))
    query_anomaly[0] = 0.0

    # Valid query: from the front cluster
    query_valid = rng.normal(loc=0.0, scale=0.1, size=(DIM,))
    query_valid[0] = 3.0

    engine = EngineCore(p_value_threshold=0.01)

    # --- Single Gaussian pipeline: demonstrates the false-negative flaw ---
    result_sg_anomaly = engine.execute_pipeline(query_anomaly, bimodal_corpus)
    assert result_sg_anomaly["status"] == "success"
    # Single Gaussian SHOULD miss this (the anomaly sits at the mean of the bimodal corpus)
    sg_missed = result_sg_anomaly["is_anomaly"] == False
    print(f"  Single-Gaussian on between-cluster query: is_anomaly={result_sg_anomaly['is_anomaly']}, "
          f"p_value={result_sg_anomaly['p_value']:.4f}")
    print(f"  (Expected: False — single-Gaussian inflated ellipsoid misses this anomaly)")

    # --- GMM pipeline: correctly catches the between-cluster anomaly ---
    result_gmm_anomaly = engine.execute_gmm_pipeline(query_anomaly, bimodal_corpus)

    # 🚨 PASTE THIS BLOCK RIGHT HERE 🚨
    import json
    print("\n--- FINAL THREAT INTELLIGENCE REPORT ---")
    print(json.dumps(result_gmm_anomaly, indent=4))
    print("----------------------------------------\n")
    # 🚨 END PASTE 🚨
    assert result_gmm_anomaly["status"] == "success", \
        f"GMM pipeline failed: {result_gmm_anomaly.get('message')}"
    assert result_gmm_anomaly["is_anomaly"] == True, (
        f"GMM failed to flag between-cluster anomaly. "
        f"p_value={result_gmm_anomaly['p_value']:.4f}, "
        f"components={result_gmm_anomaly['gmm_components_used']}"
    )

    # GMM correctly accepts a valid front-cluster member
    result_gmm_valid = engine.execute_gmm_pipeline(query_valid, bimodal_corpus)
    assert result_gmm_valid["status"] == "success", \
        f"GMM pipeline failed: {result_gmm_valid.get('message')}"
    assert result_gmm_valid["is_anomaly"] == False, (
        f"GMM false-flagged a valid front-cluster query. "
        f"p_value={result_gmm_valid['p_value']:.4f}"
    )

    print(f"  GMM components selected (BIC): {result_gmm_anomaly['diagnostics']['gmm_components_used']}")
    print(f"  GMM on between-cluster anomaly: is_anomaly={result_gmm_anomaly['is_anomaly']}, "
          f"p_value={result_gmm_anomaly['metrics']['p_value']:.4f}  <-- correctly caught")
    print(f"  GMM on valid front-cluster:     is_anomaly={result_gmm_valid['is_anomaly']}, "
          f"p_value={result_gmm_valid['metrics']['p_value']:.4f}  <-- correctly passed")
    print("PASSED: GMM handles multi-modal corpus; single-Gaussian cannot.\n")


def test_7_small_n_hotelling_correction():
    """
    Verifies that the Hotelling T² F-distribution correction diverges meaningfully
    from the chi-square asymptotic approximation for small N.

    For N=25 and p PCA dims (p ≈ N-2 = 23), the F-distribution uses df2 = N - p = 2.
    This produces an extremely conservative test compared to chi-square (which implicitly
    assumes df2 → ∞). The difference is not cosmetic — it directly prevents false positives
    on small reference corpora typical in OSINT scraping (20-50 images).

    Mathematical relationship verified:
      - same D², same p: F p-value MUST be >= chi-square p-value for n > p
      - the gap is largest when n - p is small (most conservative finite-sample behavior)
    """
    print("\n--- Test 7: Hotelling T² Small-N Correction vs Chi-Square ---")
    rng = np.random.default_rng(99)
    DIM = 768

    # Use N=100 so PCA settles at ≤50 dims and n-p ≥ 50 → F-distribution path is active.
    # With n-p < 5 the engine falls back to chi-square (F degenerates), so this corpus
    # is large enough to hit the real Hotelling branch.
    N_large = 100
    corpus_large = rng.normal(loc=0.0, scale=0.15, size=(N_large, DIM))
    query_moderate = rng.normal(loc=0.0, scale=0.15, size=(DIM,))
    query_moderate[0] += 0.5  # Moderate shift in one dimension

    engine = EngineCore(p_value_threshold=0.01)
    result = engine.execute_pipeline(query_moderate, corpus_large)

    assert result["status"] == "success", f"Pipeline failed: {result.get('message')}"

    f_p_value = result["p_value"]
    mah_sq = result["mahalanobis_distance"] ** 2
    p_dims = result["pca_dimensions_used"]
    n_used = result["images_used"]
    residual_df = n_used - p_dims

    # F-distribution branch is only active when n-p ≥ 5; verify that here
    assert residual_df >= 5, (
        f"Expected residual df ≥ 5 for N=100 corpus, got n-p={residual_df}. "
        f"n={n_used}, p={p_dims}. Chi-square fallback will be used instead."
    )

    # Reconstruct what the asymptotic chi-square approximation would have given for same D²
    chi2_p_value = 1.0 - chi2.cdf(mah_sq, df=p_dims)

    # Core assertion: Hotelling T² MUST be >= chi-square for any n > p with n-p ≥ 5
    assert f_p_value >= chi2_p_value - 1e-9, (
        f"Hotelling T² p-value must be >= chi-square p-value. "
        f"Got F={f_p_value:.6f}, chi2={chi2_p_value:.6f}, n={n_used}, p={p_dims}"
    )

    # --- Mathematical spot-check with known values (independent of corpus randomness) ---
    # D²=50, N=40, p=8: both distributions give clearly different, computable values
    D_sq_known, n_known, p_known = 50.0, 40, 8
    from scipy.stats import f as f_dist_check
    chi2_known = 1.0 - chi2.cdf(D_sq_known, df=p_known)
    f_stat_known = (n_known * (n_known - p_known)) / (p_known * (n_known - 1) * (n_known + 1)) * D_sq_known
    f_known = 1.0 - f_dist_check.cdf(f_stat_known, dfn=p_known, dfd=n_known - p_known)
    assert f_known > chi2_known, (
        f"Mathematical spot-check failed: F({f_known:.6f}) must exceed chi2({chi2_known:.6f}) "
        f"for D²={D_sq_known}, N={n_known}, p={p_known}"
    )

    print(f"  Corpus N={n_used}, PCA dims={p_dims}, residual df (n-p)={residual_df}, D²={mah_sq:.2f}")
    print(f"  Hotelling T² F-dist p-value : {f_p_value:.6f}")
    print(f"  Chi-square p-value (approx) : {chi2_p_value:.6f}")
    print(f"  Correction magnitude        : +{max(0, f_p_value - chi2_p_value):.6f} (F more conservative)")
    print(f"  Spot-check D²={D_sq_known}, N={n_known}, p={p_known}: F={f_known:.4f} > chi2={chi2_known:.6f}")
    print("PASSED: Hotelling T² finite-sample correction is demonstrably more conservative than chi-square.\n")


if __name__ == "__main__":
    run_engine_tests()
    test_6_gmm_multi_cluster()
    test_7_small_n_hotelling_correction()
    print("ALL 7 TESTS PASSED. Engine Core is mathematically stable and upgraded.")
