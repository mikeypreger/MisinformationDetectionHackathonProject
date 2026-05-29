"""
pipeline/forensic_summarizer.py  —  Phase 5: Forensic Summary Generation

Synthesizes all pipeline data into a structured LLM prompt and parses
the required VERDICT / REASONING output format.

Output contract (exact format):
    VERDICT: [VERIFIED MISINFORMATION | LIKELY MISINFORMATION | N/A | LIKELY TRUE]
    REASONING: [≤150-word paragraph]
"""

import time
import os
import re
from dotenv import load_dotenv

load_dotenv()

_VALID_VERDICTS = {"VERIFIED MISINFORMATION", "LIKELY MISINFORMATION", "N/A", "LIKELY TRUE"}

_SYSTEM = """\
You are a forensic misinformation analyst. You will receive a structured evidence dossier \
about a social media image post. Based on the dossier, produce EXACTLY this output \
(no extra text, no JSON wrapping, no markdown):

VERDICT: [choose exactly one: VERIFIED MISINFORMATION | LIKELY MISINFORMATION | N/A | LIKELY TRUE]
REASONING: [One paragraph, strictly ≤150 words. Explain what the image actually shows, \
cross-reference metadata discrepancies or statistical manifold deviations, and state the \
specific evidence that drives your confidence in the verdict.]

Verdict decision rules:
- VERIFIED MISINFORMATION: strong evidence of temporal/contextual recycling (image predates claim \
  by years, confirmed by earliest_appearance date AND statistical outlier) OR confirmed EXIF \
  timestamp mismatch against claimed event date.
- LIKELY MISINFORMATION: statistical anomaly (p_value < 0.05) OR reverse-search shows image \
  appeared significantly earlier than claimed, but not both — moderate confidence.
- LIKELY TRUE: image fits context cluster (p_value ≥ 0.05, Mahalanobis within norm), \
  reverse-search earliest date is consistent with the claimed timeframe, no EXIF conflicts.
- N/A: insufficient data (no reverse-search results, no EXIF, too few context images, \
  or image quality blocked earlier stage).
"""


def _build_dossier(
    caption: str,
    image_metadata: dict,
    stats: dict,
    reverse_search: dict,
<<<<<<< HEAD
    gemini_label: str = "",
    gemini_explanation: str = "",
=======
>>>>>>> db50590cf0fbec53148d22784c379e261240607a
) -> str:
    """Construct the evidence dossier text fed to the LLM."""
    mahal     = stats.get("mahalanobis_distance")
    p_val     = stats.get("p_value")
    pca_dims  = stats.get("pca_components_used")
    ctx_count = stats.get("context_images_embedded", stats.get("context_images_fetched"))
    emb_dim   = 768  # DINOv2 ViT-B/14

    retention_ratio = (
        f"{pca_dims}/{emb_dim} = {pca_dims / emb_dim:.3f}"
        if pca_dims else "N/A"
    )

    earliest = reverse_search.get("earliest_appearance") or {}
    appearances = reverse_search.get("all_appearances", [])
    matched_domains = list({
        a.get("source_name", "") for a in appearances if a.get("source_name")
    })[:10]

    lines = [
        "=== EVIDENCE DOSSIER ===",
        "",
        f"POST CAPTION: {caption or '(none)'}",
        "",
        "--- IMAGE METADATA (EXIF) ---",
        f"  Capture timestamp : {image_metadata.get('datetime_original') or 'Stripped / not available'}",
        f"  Camera make       : {image_metadata.get('camera_make') or 'N/A'}",
        f"  Camera model      : {image_metadata.get('camera_model') or 'N/A'}",
        f"  GPS coordinates   : {_fmt_gps(image_metadata)}",
        "",
        "--- STATISTICAL FORENSICS ---",
        f"  Mahalanobis Distance (D²)  : {f'{mahal:.4f}' if mahal is not None else 'N/A'}",
        f"  Chi-Square p-value          : {f'{p_val:.6f}' if p_val is not None else 'N/A'}",
        f"  Statistical anomaly flag    : {stats.get('is_anomaly', 'N/A')}",
        f"  PCA Manifold Retention Ratio: {retention_ratio}",
        f"  Context images used         : {ctx_count or 'N/A'}",
        "",
        "--- REVERSE IMAGE SEARCH ---",
        f"  Search confidence : {reverse_search.get('search_confidence', 'N/A')}",
        f"  Earliest known date   : {earliest.get('date') or 'Not found'}",
        f"  Earliest source URL   : {earliest.get('url') or 'N/A'}",
        f"  Earliest source name  : {earliest.get('source_name') or 'N/A'}",
        f"  Earliest page title   : {earliest.get('title') or 'N/A'}",
        f"  Total web appearances : {len(appearances)}",
        f"  Matched domains (top 10): {', '.join(matched_domains) if matched_domains else 'None'}",
    ]
<<<<<<< HEAD

    if gemini_label or gemini_explanation:
        lines += [
            "",
            "--- GEMINI VISUAL ASSESSMENT ---",
            f"  Label       : {gemini_label or 'N/A'}",
            f"  Explanation : {gemini_explanation or 'N/A'}",
        ]

=======
>>>>>>> db50590cf0fbec53148d22784c379e261240607a
    return "\n".join(lines)


def _fmt_gps(meta: dict) -> str:
    lat, lon = meta.get("gps_lat"), meta.get("gps_lon")
    if lat is not None and lon is not None:
        return f"{lat}, {lon}"
    return "N/A"


def _parse_response(text: str) -> dict:
    """Extract VERDICT and REASONING from the LLM's plain-text response."""
    verdict  = "N/A"
    reasoning = ""

    verdict_match = re.search(r"VERDICT\s*:\s*(.+)", text, re.IGNORECASE)
    if verdict_match:
        candidate = verdict_match.group(1).strip().upper()
        # Accept even if the model wrapped it in brackets
        candidate = candidate.strip("[]")
        if candidate in _VALID_VERDICTS:
            verdict = candidate
        else:
            # Try partial match
            for v in _VALID_VERDICTS:
                if v in candidate:
                    verdict = v
                    break

    reasoning_match = re.search(r"REASONING\s*:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    if reasoning_match:
        raw = reasoning_match.group(1).strip()
        # Enforce 150-word cap
        words = raw.split()
        reasoning = " ".join(words[:150])

    return {"verdict": verdict, "reasoning": reasoning}

def generate_forensic_summary(
    caption: str,
    image_metadata: dict,
    stats: dict,
    reverse_search: dict,
<<<<<<< HEAD
    gemini_label: str = "",
    gemini_explanation: str = "",
=======
>>>>>>> db50590cf0fbec53148d22784c379e261240607a
) -> dict:
    """
    Asks Gemini to produce the summary, with an automatic retry 
    and fallback loop to beat 503 server overloads.
    """
    _fallback = {"verdict": "N/A", "reasoning": "Forensic LLM unavailable."}

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return _fallback

<<<<<<< HEAD
    dossier = _build_dossier(caption, image_metadata, stats, reverse_search, gemini_label, gemini_explanation)
=======
    dossier = _build_dossier(caption, image_metadata, stats, reverse_search)
>>>>>>> db50590cf0fbec53148d22784c379e261240607a

    try:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=api_key)
        
        # List of models to try in order if one throws a 503 error
        models_to_try = ["gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
        
        for model_name in models_to_try:
            for attempt in range(2): # Try each model twice before moving on
                try:
                    resp = client.models.generate_content(
                        model=model_name,
                        contents=dossier,
                        config=genai_types.GenerateContentConfig(
                            system_instruction=_SYSTEM,
                            temperature=0,
                        ),
                    )
                    # If successful, return immediately!
                    return _parse_response(resp.text)
                except Exception as e:
                    print(f"[forensic_summarizer] {model_name} (attempt {attempt+1}) failed: {e}. Retrying...")
                    time.sleep(1) # Wait 1 second before retrying
                    
        return _fallback
    except Exception as e:
        print(f"[forensic_summarizer] Critical collapse: {e}")
        return _fallback