"""
pipeline/council.py  —  Phase 5: Asymmetric Cascading Veto Engine

Replaces generate_verdict() + generate_forensic_summary() with three concurrent LLM
personas aggregated via hard-veto logic.

A single persona score >= 85 overrides consensus to VERIFIED MISINFORMATION.
"""

import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dotenv import load_dotenv

import numpy as np

load_dotenv()

# ── Scoring thresholds ────────────────────────────────────────────────────────
_VETO_THRESHOLD           = 85
_LIKELY_MISINFO_THRESHOLD = 65
_UNCERTAIN_THRESHOLD      = 35
_FALLBACK_SCORE           = 50
_PERSONA_TIMEOUT_SECS     = 30

# ── Simulation constants (imported by MyApp.py for synthetic embedding injection) ──
_SIM_CONTEXT_EMBEDDINGS = np.random.default_rng(42).standard_normal((25, 768)).astype(np.float32)
_SIM_QUERY_EMBEDDING    = np.random.default_rng(99).standard_normal((768,)).astype(np.float32)
_SIM_CAPTION_SIM        = 0.21

# ── Simulation result: full UI-safe dict, no network calls ────────────────────
_SIMULATION_RESULT = {
    "gemini_label":      "🔍 UNCERTAIN",
    "gemini_confidence": 55,
    "gemini_explanation": (
        "[SIMULATION] The Historian notes the image appeared 8 months before the "
        "caption's claimed event, raising moderate temporal concerns."
    ),
    "forensic_verdict": "N/A",
    "forensic_reasoning": (
        "[SIMULATION MODE] [Statistical Cynic, score 45] p-value of 0.12 places the "
        "image within the normal context cluster; no statistical anomaly detected. "
        "[Historian, score 62] Reverse search found the image 8 months before the "
        "claimed event on a regional news site, suggesting possible reuse. "
        "[Linguist, score 58] CLIP similarity of 0.21 is borderline; the caption "
        "references a specific location not clearly confirmed by visual content."
    ),
    "council_veto_triggered": False,
    "council_veto_persona":   None,
    "council_scores": {
        "statistical_cynic": 45,
        "historian":         62,
        "linguist":          58,
    },
    "council_mean_score": 55.0,
}

# ── Persona system prompts ────────────────────────────────────────────────────

_CYNIC_SYSTEM = """\
You are the Statistical Cynic — a forensic analyst who trusts math over narrative.

You receive detection statistics from an anomaly detection pipeline that embedded a social media
image using DINOv2 ViT-B/14 (768-D), then measured how far the image sits from its topic
context cluster using Mahalanobis distance and a chi-square / Hotelling T² p-value.

Your task: assign a SINGLE integer risk score (0–100) representing how likely it is that the
image is a statistical anomaly — a signal it may have been misappropriated from a different context.

Scoring rules (apply the FIRST matching rule):
1. is_anomaly=True AND p_value < 0.01                                 → score 80–95
2. is_anomaly=True AND p_value 0.01–0.05                              → score 60–79
3. is_anomaly=False AND mahalanobis_distance within normal range       → score 10–35
4. outliers_removed_by_mad is large (> 30% of pool size hinted by pca_components_used) → raise score +10
5. pca_components_used < 5                                             → score toward 40–60 (too little data)
6. Any critical input is None                                          → score 50, assessment "Insufficient statistical data."

Return ONLY valid JSON with no markdown fences:
{"score": <integer 0-100>, "assessment": "<one or two sentences citing specific numbers>"}
"""

_HISTORIAN_SYSTEM = """\
You are the Historian — a chronology specialist who detects temporal recycling of images.

Temporal recycling: an old image reposted with a caption claiming it depicts a recent event.
This is one of the most common forms of misinformation.

CRITICAL TIMELINE ANCHOR: Today's date is May 31, 2026. Use this as your absolute baseline
for calculating whether an image's publication date predates an event.

⚠️  STRICT DATA RULE: You MUST work ONLY with the reverse-image-search data provided in
the user message below. Do NOT draw on your training knowledge about where specific images
have appeared online. Do NOT invent, recall, or infer any dates, URLs, source names, or
article titles beyond what is explicitly listed. If the provided date says "Not found",
treat it as genuinely unknown and score exactly 45 — you are FORBIDDEN from substituting
any date or source from your own memory.

Your task: compare the image's earliest known publication date to the event the caption claims.
Determine whether the image predates the claimed event significantly.

Scoring rules (apply the FIRST matching rule):
1. Earliest date clearly predates the caption's claimed event by 2+ years        → score 85–95
2. Earliest date predates by 6 months to 2 years                                 → score 60–80
3. Earliest date is consistent with or after the claimed event                   → score 10–30
4. earliest_appearance date is "Not found" / None                                → score 45 (uncertain, not exonerating)
5. Caption has no datable claim                                                  → score 40
Modifier: if source name or title clearly describes a different event/location than caption → add +10

Return ONLY valid JSON with no markdown fences. Cite ONLY data that appears in the provided search results — never cite training memory:
{"score": <integer 0-100>, "assessment": "<one or two sentences citing ONLY data from the provided search results>"}
"""

_LINGUIST_SYSTEM = """\
You are the Linguist — a multimodal semantics expert who detects caption-image mismatches.

You receive the image itself, its caption, and a CLIP cosine similarity score (range –1 to 1,
where >= 0.28 means strong semantic alignment; < 0.20 means weak or mismatched).

Your task: determine whether the caption misrepresents what is visually depicted.
Do NOT assume a claim is false just because the image lacks explicit proof; reserve extreme
scores (85+) ONLY for explicit visual contradictions.

Scoring rules (apply the FIRST matching rule):
1. DIRECT CONTRADICTION: Image content visibly disproves the caption             → score 85–100
2. UNSUPPORTED: Caption claims specific things/events not visible in the image   → score 60–84
3. CLIP score < 0.20 AND image content feels disconnected from the caption       → score 60–84
4. Official graphics (logos, announcement cards) naturally score 0.18–0.24 on CLIP;
   do NOT penalise those unless image content clearly contradicts caption text
5. CLIP score >= 0.28 AND image content matches caption                          → score 5–25
6. caption_image_similarity is None → rely only on visual analysis               → score 35–55
7. Empty caption                                                                 → score 30

Return ONLY valid JSON with no markdown fences:
{"score": <integer 0-100>, "assessment": "<one or two sentences citing specific visual or textual evidence>"}
"""

# ── Gemini client singleton ───────────────────────────────────────────────────

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set")
        from google import genai
        _client = genai.Client(api_key=api_key)
    return _client


# ── JSON parsing helper ───────────────────────────────────────────────────────

def _safe_parse(raw: str) -> dict:
    """Parse persona JSON response; returns fallback dict on any error."""
    try:
        data  = json.loads(raw)
        score = max(0, min(100, int(data.get("score", _FALLBACK_SCORE))))
        return {"score": score, "assessment": str(data.get("assessment", ""))}
    except Exception:
        return {"score": _FALLBACK_SCORE, "assessment": "(parse error)"}


# ── Persona callers ───────────────────────────────────────────────────────────

def _call_statistical_cynic(
    p_value,
    mahalanobis_distance,
    is_anomaly,
    pca_components_used,
    outliers_removed_by_mad,
) -> dict:
    from google.genai import types as genai_types

    client   = _get_client()
    user_msg = (
        f"Statistical detection results:\n"
        f"- is_anomaly: {is_anomaly}\n"
        f"- p_value: {p_value}\n"
        f"- mahalanobis_distance: {mahalanobis_distance}\n"
        f"- pca_components_used: {pca_components_used}\n"
        f"- outliers_removed_by_mad: {outliers_removed_by_mad}\n"
    )
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_msg,
        config=genai_types.GenerateContentConfig(
            system_instruction=_CYNIC_SYSTEM,
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    return _safe_parse(resp.text)


def _call_historian(
    earliest_appearance: dict | None,
    caption: str,
) -> dict:
    from google.genai import types as genai_types

    client = _get_client()
    if earliest_appearance:
        ea_date   = earliest_appearance.get("date",        "Not found")
        ea_source = earliest_appearance.get("source_name", "N/A")
        ea_url    = earliest_appearance.get("url",         "N/A")
        ea_title  = earliest_appearance.get("title",       "N/A")
    else:
        ea_date = ea_source = ea_url = ea_title = "Not found"

    user_msg = (
        f"Caption: {caption or '(none)'}\n\n"
        f"Reverse image search earliest appearance:\n"
        f"- Date: {ea_date}\n"
        f"- Source: {ea_source}\n"
        f"- URL: {ea_url}\n"
        f"- Page title: {ea_title}\n"
    )
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_msg,
        config=genai_types.GenerateContentConfig(
            system_instruction=_HISTORIAN_SYSTEM,
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    return _safe_parse(resp.text)


def _call_linguist(
    caption: str,
    image_url: str,
    caption_image_similarity: float | None,
) -> dict:
    from google.genai import types as genai_types

    client    = _get_client()
    text_part = (
        f"Caption: {caption or '(none)'}\n"
        f"CLIP caption-image similarity score: {caption_image_similarity}\n\n"
        "Assess whether this caption misrepresents what the image shows."
    )

    try:
        img_resp     = requests.get(image_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        img_resp.raise_for_status()
        image_bytes  = img_resp.content
        ext          = image_url.split("?")[0].rsplit(".", 1)[-1].lower()
        mime_type    = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png",  "webp": "image/webp",
        }.get(ext, "image/jpeg")
        contents = [
            genai_types.Part(
                inline_data=genai_types.Blob(data=image_bytes, mime_type=mime_type)
            ),
            genai_types.Part(text=text_part),
        ]
    except Exception:
        contents = text_part  # text-only fallback when image download fails

    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=genai_types.GenerateContentConfig(
            system_instruction=_LINGUIST_SYSTEM,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _safe_parse(resp.text)


# ── Verdict aggregation ───────────────────────────────────────────────────────

def _aggregate(scores: dict) -> dict:
    """Apply veto logic; return verdict fields."""
    veto_persona = None
    for name, score in scores.items():
        if score >= _VETO_THRESHOLD:
            veto_persona = name
            break

    mean_score = sum(scores.values()) / len(scores)

    if veto_persona:
        forensic_verdict = "VERIFIED MISINFORMATION"
        gemini_label     = "🚨 VERIFIED MISINFORMATION"
        veto_triggered   = True
        mean_score       = max(scores.values())
    elif mean_score >= _LIKELY_MISINFO_THRESHOLD:
        forensic_verdict = "LIKELY MISINFORMATION"
        gemini_label     = "⚠️ LIKELY MISINFORMATION"
        veto_triggered   = False
    elif mean_score >= _UNCERTAIN_THRESHOLD:
        forensic_verdict = "N/A"
        gemini_label     = "🔍 UNCERTAIN"
        veto_triggered   = False
    else:
        forensic_verdict = "LIKELY TRUE"
        gemini_label     = "✅ LIKELY TRUE"
        veto_triggered   = False

    return {
        "forensic_verdict":       forensic_verdict,
        "gemini_label":           gemini_label,
        "council_veto_triggered": veto_triggered,
        "council_veto_persona":   veto_persona,
        "council_mean_score":     round(mean_score, 1),
    }


def _build_reasoning(scores: dict, assessments: dict) -> str:
    """Build forensic_reasoning <=150 words from persona assessments."""
    parts = []
    for name, score in scores.items():
        label      = name.replace("_", " ").title()
        assessment = assessments.get(name, "")
        parts.append(f"[{label}, score {score}] {assessment}")
    words = " ".join(parts).split()
    return " ".join(words[:150])


def _build_explanation(scores: dict, assessments: dict, veto_persona: str | None) -> str:
    """Return 1-sentence explanation from the highest-scoring persona."""
    if veto_persona and assessments.get(veto_persona):
        return assessments[veto_persona]
    if not scores:
        return "Council analysis inconclusive."
    best_name = max(scores, key=scores.get)
    return assessments.get(best_name) or "Council analysis inconclusive."


def _build_neutral_fallback(reason: str) -> dict:
    """All-keys-present neutral dict when the council cannot run at all."""
    return {
        "gemini_label":           "❓ UNKNOWN",
        "gemini_confidence":      0,
        "gemini_explanation":     f"Council unavailable: {reason}",
        "forensic_verdict":       "N/A",
        "forensic_reasoning":     f"Council unavailable: {reason}",
        "council_veto_triggered": False,
        "council_veto_persona":   None,
        "council_scores": {
            "statistical_cynic": _FALLBACK_SCORE,
            "historian":         _FALLBACK_SCORE,
            "linguist":          _FALLBACK_SCORE,
        },
        "council_mean_score": float(_FALLBACK_SCORE),
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def run_council(
    caption: str,
    image_url: str,
    stats: dict,
    reverse_search: dict | None,
    caption_image_similarity: float | None,
    simulation_mode: bool = False,
) -> dict:
    """
    Run the 3-persona concurrent veto engine.
    Returns a dict compatible with MyApp.py (backward-compatible + new council keys).
    """
    if simulation_mode:
        return _SIMULATION_RESULT.copy()

    if not os.getenv("GOOGLE_API_KEY"):
        return _build_neutral_fallback("No GOOGLE_API_KEY set")

    earliest_appearance = (
        reverse_search.get("earliest_appearance") if reverse_search else None
    )

    scores      = {}
    assessments = {}

    persona_calls = {
        "statistical_cynic": (
            _call_statistical_cynic,
            (
                stats.get("p_value"),
                stats.get("mahalanobis_distance"),
                stats.get("is_anomaly"),
                stats.get("pca_components_used"),
                stats.get("outliers_removed_by_mad"),
            ),
        ),
        "historian": (
            _call_historian,
            (earliest_appearance, caption),
        ),
        "linguist": (
            _call_linguist,
            (caption, image_url, caption_image_similarity),
        ),
    }

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            name: executor.submit(fn, *args)
            for name, (fn, args) in persona_calls.items()
        }
        for name, future in futures.items():
            try:
                result            = future.result(timeout=_PERSONA_TIMEOUT_SECS)
                scores[name]      = max(0, min(100, int(result.get("score", _FALLBACK_SCORE))))
                assessments[name] = str(result.get("assessment", ""))
                print(f"[council] {name}: score={scores[name]}")
            except FuturesTimeoutError:
                print(f"[council] {name} timed out after {_PERSONA_TIMEOUT_SECS}s")
                scores[name]      = _FALLBACK_SCORE
                assessments[name] = f"({name} timed out)"
            except Exception as e:
                print(f"[council] {name} failed: {e}")
                scores[name]      = _FALLBACK_SCORE
                assessments[name] = f"({name} unavailable)"

    agg                = _aggregate(scores)
    forensic_reasoning = _build_reasoning(scores, assessments)
    gemini_explanation = _build_explanation(scores, assessments, agg["council_veto_persona"])

    return {
        "gemini_label":           agg["gemini_label"],
        "gemini_confidence":      int(round(agg["council_mean_score"])),
        "gemini_explanation":     gemini_explanation,
        "forensic_verdict":       agg["forensic_verdict"],
        "forensic_reasoning":     forensic_reasoning,
        "council_veto_triggered": agg["council_veto_triggered"],
        "council_veto_persona":   agg["council_veto_persona"],
        "council_scores":         scores,
        "council_mean_score":     agg["council_mean_score"],
    }
