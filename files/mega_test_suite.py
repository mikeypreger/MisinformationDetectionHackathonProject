import os
import sys
import numpy as np

# Path routing to ensure we hit your local engine_core
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from engine_core import EngineCore

def run_mega_validation_matrix():
    print("======================================================")
    print("🚀 INITIATING ASTRODETECT R&D VERIFICATION MATRIX 🚀")
    print("======================================================\n")
    
    engine = EngineCore(p_value_threshold=0.01)
    rng = np.random.default_rng(101)
    DIM = 768

    # ---------------------------------------------------------
    # TEST A: Zero-Variance Collapse (The "Identical" Edge Case)
    # ---------------------------------------------------------
    print("Test A: Zero-Variance Dimensionality Collapse")
    # What happens if a bot scrapes the EXACT same image 30 times?
    # Variance is 0. PCA and Covariance matrices usually explode trying to divide by zero.
    identical_vector = rng.normal(loc=0.5, scale=0.1, size=(DIM,))
    zero_var_corpus = np.tile(identical_vector, (30, 1))
    
    query_exact = identical_vector.copy()
    query_shifted = identical_vector.copy() + 0.1
    
    res_exact = engine.execute_gmm_pipeline(query_exact, zero_var_corpus)
    res_shifted = engine.execute_gmm_pipeline(query_shifted, zero_var_corpus)
    
    # We expect success statuses. The math should handle 0 variance gracefully via epsilon fallbacks.
    assert res_exact["status"] == "success", f"Failed exact match on 0-variance: {res_exact}"
    assert res_shifted["status"] == "success", f"Failed shifted match on 0-variance: {res_shifted}"
    print("✅ PASSED. Engine survived singular zero-variance matrix inversion without NaN crashing.")

# ---------------------------------------------------------
    # TEST B: Covariance Correlation Anomaly (The "Shape" Exploit)
    # ---------------------------------------------------------
    print("\nTest B: Covariance Correlation Anomaly (The 'Shape' Exploit)")
    # We drop background noise to 0.01 so PCA strictly focuses on Dim 0 and Dim 1.
    base_corpus = rng.normal(loc=0.0, scale=0.01, size=(100, DIM))
    
    # We create an ellipse: wide on Dim 0, but 4x narrower on Dim 1.
    base_corpus[:, 0] = rng.normal(loc=0.0, scale=2.0, size=100) 
    base_corpus[:, 1] = rng.normal(loc=0.0, scale=0.5, size=100) 
    
    shape_anomaly = rng.normal(loc=0.0, scale=0.01, size=(DIM,))
    shape_anomaly[0] = 2.0  # Just 1 standard deviation away (Totally normal)
    shape_anomaly[1] = 3.0  # 6 standard deviations away! (Massive geometric violation)
    
    res_shape = engine.execute_pipeline(shape_anomaly, base_corpus)
    
    assert res_shape["is_anomaly"] == True, "Failed to catch the covariance shape exploit."
    assert res_shape["p_value"] < 0.01
    print(f"✅ PASSED. Mahalanobis correctly scaled inverse variance to catch the hidden exploit. (p-value: {res_shape['p_value']:.4f})")

    # ---------------------------------------------------------
    # TEST C: GMM Component Starvation Guard
    # ---------------------------------------------------------
    print("\nTest C: GMM Component Starvation")
    # If we only have 12 images, the BIC might try to fit 3 clusters (4 images each).
    # A covariance matrix for 4 images in high-dim space is catastrophically unstable.
    # The engine should strictly cap the GMM to 1 component (12 // 10 = 1).
    starvation_corpus = rng.normal(loc=0.5, scale=0.1, size=(12, DIM))
    query_starvation = rng.normal(loc=0.5, scale=0.1, size=(DIM,))
    
    res_starve = engine.execute_gmm_pipeline(query_starvation, starvation_corpus)
    
    assert res_starve["status"] == "success"
    assert res_starve["diagnostics"]["gmm_components_used"] == 1, "Engine allowed GMM components to exceed safe mathematical limits!"
    print(f"✅ PASSED. Engine dynamically restricted GMM components to {res_starve['diagnostics']['gmm_components_used']} to preserve covariance stability.")

    # ---------------------------------------------------------
    # TEST D: The 40% Corruption Ratio (Severe Poisoning)
    # ---------------------------------------------------------
    print("\nTest D: Severe Baseline Poisoning (40% Garbage)")
    # MAD breaks down theoretically at 50% contamination. We push it to 40%.
    # 60 clean images, 40 completely chaotic scraper artifacts.
    clean_images = rng.normal(loc=1.0, scale=0.1, size=(60, DIM))
    garbage_images = rng.normal(loc=20.0, scale=10.0, size=(40, DIM))
    heavily_poisoned_corpus = np.vstack([clean_images, garbage_images])
    
    query_clean = rng.normal(loc=1.0, scale=0.1, size=(DIM,))
    
    res_poison = engine.execute_gmm_pipeline(query_clean, heavily_poisoned_corpus)
    
    assert res_poison["status"] == "success"
    assert res_poison["diagnostics"]["images_filtered"] >= 35, "MAD Filter failed to purge the severe poisoning attack."
    assert res_poison["is_anomaly"] == False, "Poisoning successfully corrupted the baseline and caused a false positive."
    print(f"✅ PASSED. MAD Filter correctly identified and shredded {res_poison['diagnostics']['images_filtered']} garbage tensors before they could touch the GMM.")

# ---------------------------------------------------------
    # TEST E: High-Volume Dimensionality Capping
    # ---------------------------------------------------------
    print("\nTest E: High-Volume Dimensionality Capping")
    # Simulate 500 images with actual structural patterns in the first 30 dimensions
    # and minimal ambient noise in the remaining 738 dimensions.
    structured_core = rng.normal(loc=1.0, scale=2.0, size=(500, 30))
    ambient_noise = rng.normal(loc=0.0, scale=0.05, size=(500, DIM - 30))
    massive_corpus = np.hstack([structured_core, ambient_noise])
    
    query_massive = np.hstack([rng.normal(loc=1.0, scale=2.0, size=(30,)), 
                               rng.normal(loc=0.0, scale=0.05, size=(DIM - 30,))])
    
    res_massive = engine.execute_gmm_pipeline(query_massive, massive_corpus)
    
    assert res_massive["status"] == "success"
    assert res_massive["diagnostics"]["pca_dimensions_used"] <= 50, "PCA cap failed. Engine allowed unsafe expansion."
    print(f"✅ PASSED. System safely capped subspace at {res_massive['diagnostics']['pca_dimensions_used']} dimensions for N={res_massive['diagnostics']['images_used']}.")

if __name__ == "__main__":
    run_mega_validation_matrix()