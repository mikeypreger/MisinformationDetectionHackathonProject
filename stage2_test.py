import io
import json
import numpy as np
from PIL import Image
from stage2 import Stage2WeakPriors

def run_stage2_mega_test():
    print("======================================================")
    print("🛡️ INITIATING STAGE 2 GUARDRAIL VERIFICATION MATRIX 🛡️")
    print("======================================================\n")
    
    # Initialize the engine
    analyzer = Stage2WeakPriors()
    
    # ---------------------------------------------------------
    # TEST A: The HTML/Webpage Trap (Network Level)
    # ---------------------------------------------------------
    print("\nTest A: The HTML Webpage Trap")
    # We feed it a standard webpage URL instead of an image URL.
    # It should hit Guardrail 1 and abort before crashing PIL.
    res_a = analyzer.process_evidence(
        "https://example.com", 
        "A test caption"
    )
    assert res_a["stage_status"] == "FAILED_NETWORK_OR_NOT_IMAGE", f"Failed to block HTML! Status: {res_a['stage_status']}"
    print("✅ PASSED. Network guardrail successfully identified and blocked an HTML response.")

    # ---------------------------------------------------------
    # TEST B: The Pitch-Black / Zero Variance Image
    # ---------------------------------------------------------
    print("\nTest B: Pitch-Black Image (Zero Variance)")
    # We generate a pure black 200x200 image in memory and intercept the fetcher.
    black_img = Image.new('RGB', (200, 200), color='black')
    img_byte_arr = io.BytesIO()
    black_img.save(img_byte_arr, format='PNG')
    
    # Temporarily monkey-patch the fetcher to return our trap bytes
    original_fetch = analyzer.fetch_image_from_url
    analyzer.fetch_image_from_url = lambda url, use_proxy=False: img_byte_arr.getvalue()
    
    res_b = analyzer.process_evidence("http://fake-black-url.com", "caption")
    
    assert res_b["stage_status"] == "FAILED_UNREADABLE_IMAGE", "Failed to catch the black image!"
    print("✅ PASSED. Mathematical variance filter caught the pitch-black image (var < 5.0).")

    # ---------------------------------------------------------
    # TEST C: The Corrupted Byte Stream
    # ---------------------------------------------------------
    print("\nTest C: Corrupted Binary Data")
    # We feed it complete binary garbage that claims to be an image.
    analyzer.fetch_image_from_url = lambda url, use_proxy=False: b"This is just random text data, not a PNG header!"
    
    res_c = analyzer.process_evidence("http://fake-corrupt-url.com", "caption")
    
    assert res_c["stage_status"] == "FAILED_CORRUPT_BYTES", "Failed to catch the UnidentifiedImageError!"
    print("✅ PASSED. Structural byte-check successfully intercepted and contained a corrupted file.")

    # ---------------------------------------------------------
    # TEST D: The Valid Image (Happy Path)
    # ---------------------------------------------------------
    print("\nTest D: Valid Image Analysis")
    # Restore the real fetcher
    analyzer.fetch_image_from_url = original_fetch
    
    res_d = analyzer.process_evidence(
        "https://cdn.britannica.com/37/252437-050-F21BD210/Taylor-Swift-performs-The-Eras-Tour-Sao-Paulo-Brazil-2023.jpg",
        "singer performing on stage"
    )
    
    assert res_d["stage_status"] == "COMPLETED", "Valid image failed processing!"
    assert isinstance(res_d["clip_friction_score"], float), "CLIP score was not calculated!"
    print(f"✅ PASSED. Stage 2 successfully processed a valid image. (CLIP Score: {res_d['clip_friction_score']})")

    print("\n======================================================")
    print("🏆 ALL STAGE 2 GUARDRAIL TESTS PASSED. ENGINE IS SECURE. 🏆")
    print("======================================================")

if __name__ == "__main__":
    run_stage2_mega_test()