"""
pipeline/council.py  —  Phase 5: Parallel LLM Council with Averaged Scoring

All three personas receive identical full-context input (image + all signals) and fire
concurrently. Final verdict is a simple average of their scores — no hard veto.

Why no hard veto: a single persona fixating on one signal (e.g. an old image date) while
two others correctly read the full context as authentic would cause a false positive.
Averaging weights all three perspectives equally.
"""

import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dotenv import load_dotenv

import numpy as np

load_dotenv()

# ── Score thresholds (applied to mean of 3 persona scores) ───────────────────
_SCORE_VERIFIED  = 65   # mean >= → VERIFIED MISINFORMATION
_SCORE_LIKELY    = 45   # mean >= → LIKELY MISINFORMATION
_SCORE_UNCERTAIN = 25   # mean >= → N/A / Uncertain
_FALLBACK_SCORE  = 50
_PERSONA_TIMEOUT = 25   # seconds per persona before we fall back to neutral

# ── Simulation constants — imported by MyApp.py for synthetic embedding injection ──
_SIM_CONTEXT_EMBEDDINGS = np.random.default_rng(42).standard_normal((25, 768)).astype(np.float32)
_SIM_QUERY_EMBEDDING    = np.random.default_rng(99).standard_normal((768,)).astype(np.float32)
_SIM_CAPTION_SIM        = 0.21

_SIMULATION_RESULT = {
    "gemini_label":      "🔍 UNCERTAIN",
    "gemini_confidence": 45,
    "gemini_explanation": "[SIMULATION] Moderate temporal concern; visual content matches caption.",
    "forensic_verdict":  "N/A",
    "forensic_reasoning": (
        "[SIMULATION] Statistical Cynic (35): no anomaly detected, p-value 0.12. "
        "Historian (55): image appeared 8 months before claimed event on regional news. "
        "Linguist (45): borderline CLIP score 0.21, caption references location not clearly visible."
    ),
    "council_veto_triggered": False,
    "council_veto_persona":   None,
    "council_scores":    {"statistical_cynic": 35, "historian": 55, "linguist": 45},
    "council_mean_score": 45.0,
    "top_reasons": [
        "Image appeared 8 months before the event it claims to depict.",
        "Caption references a location not clearly visible in the photograph.",
        "CLIP caption-image similarity score of 0.21 falls below the confident-match threshold.",
    ],
}

# ── System prompts — same full context, different analytical lens ─────────────

_CYNIC_SYSTEM = """\
You are a skeptical forensic analyst examining a social media post for misinformation.
You receive the post image, its caption, statistical anomaly detection scores,
reverse image search provenance data, and a CLIP caption-image similarity score.

Evaluate ALL signals holistically and assign a single risk score 0-100.

Scoring guide:
  0-24   Almost certainly authentic / correctly captioned
  25-44  Probably authentic, minor concerns
  45-64  Genuinely ambiguous — signals conflict
  65-84  Likely misinformation — most signals point to misuse
  85-100 Almost certainly misinformation — strong cross-signal evidence

Key calibration rules:
- p_value close to 1.0 means the image FITS its context pool (not suspicious at all).
- p_value < 0.05 AND is_anomaly=True → statistical flag, raises score.
- CLIP score < 0.22 is only suspicious if image content also mismatches the caption.
  News graphics, broadcast screenshots, and announcement cards naturally score 0.18-0.24 — do not penalise them.
- Temporal recycling is misinformation ONLY when the caption claims a RECENT event
  that postdates the image's known origin. A news graphic referencing an old event is NOT recycling.
- Multiple weak signals together outweigh one strong signal in isolation.

CRITICAL — reverse image search reliability:
- Reverse image search finds VISUALLY SIMILAR images, not necessarily THE SAME image.
  A plane crash in India can look nearly identical to one in Ukraine. A protest crowd in one
  country resembles a protest in another. NEVER treat a reverse-search match as proof of
  identity — it is a lead, not a verdict.
- If the found earliest-appearance URL/title describes a DIFFERENT country, language, or
  event type than the caption, there is a real possibility the search matched a different
  but visually similar image. In that case, lower your confidence significantly.
- search_confidence is provided. If it is "medium" or "low", treat the reverse image search
  as weak corroborating evidence only, not primary evidence.
- A score above 80 requires AT LEAST TWO independent signals pointing to misinformation
  (e.g. statistical anomaly + early date + CLIP mismatch). Reverse image search alone,
  no matter how striking, caps your score at 75 unless confirmed by other signals.

Return ONLY valid JSON, no markdown fences:
{"score": <integer 0-100>, "assessment": "<2-3 sentences citing the most important evidence>"}
"""

_HISTORIAN_SYSTEM = """\
You are a provenance and timeline specialist examining a social media post for misinformation.
You receive the post image, its caption, statistical anomaly detection scores,
reverse image search provenance data, and a CLIP caption-image similarity score.

Evaluate ALL signals holistically and assign a single risk score 0-100.

Scoring guide:
  0-24   Almost certainly authentic / correctly captioned
  25-44  Probably authentic, minor concerns
  45-64  Genuinely ambiguous — signals conflict
  65-84  Likely misinformation — most signals point to misuse
  85-100 Almost certainly misinformation — strong cross-signal evidence

CRITICAL temporal recycling rules:
- An image is only suspicious if the caption claims it shows a RECENT event
  AND the image is known to predate that event by a significant margin.
- If the image is a news broadcast graphic, screenshot, or article thumbnail that EXPLICITLY
  DISPLAYS the caption text or shows a public figure referenced in the caption,
  it is almost certainly NOT misinformation — score 0-20.
- If earliest_appearance = "Not found", score neutrally (35-45) — absence of data is not evidence.
- Archive images reposted with accurate captions describing WHEN they are from are not misinformation.
- Cross-check the page title and source: if the original publication aligns with the caption's claim,
  score low regardless of date gap.

CRITICAL — reverse image search is a lead, not proof:
- Reverse image search returns VISUALLY SIMILAR images. The matched image may be a different
  photograph of a similar scene (same type of event, different country, different year).
  A military aircraft crash in one country looks nearly identical to one in another.
  You must not conclude the found image IS the post image — only that they are similar.
- If the earliest-appearance source describes a completely different geographic region or event
  type than the caption claims, there is a HIGH chance this is a false match. Score this
  scenario no higher than 55-65 (ambiguous) unless other independent signals also flag it.
- If search_confidence is "medium" or "low", the reverse image search is weak evidence.
  Do not assign a score above 60 based on it alone.
- A score above 80 requires the reverse image search match AND at least one other independent
  corroborating signal (statistical anomaly, CLIP mismatch, or clear caption inconsistency
  visible in the image itself). Provenance alone cannot justify scores above 75.

Return ONLY valid JSON, no markdown fences:
{"score": <integer 0-100>, "assessment": "<2-3 sentences focusing on temporal and provenance evidence>"}
"""

_LINGUIST_SYSTEM = """\
You are a multimodal semantics analyst examining a social media post for misinformation.
You receive the post image, its caption, statistical anomaly detection scores,
reverse image search provenance data, and a CLIP caption-image similarity score.

Evaluate ALL signals holistically and assign a single risk score 0-100.

Scoring guide:
  0-24   Almost certainly authentic / correctly captioned
  25-44  Probably authentic, minor concerns
  45-64  Genuinely ambiguous — signals conflict
  65-84  Likely misinformation — most signals point to misuse
  85-100 Almost certainly misinformation — strong cross-signal evidence

Key rules for caption-image alignment:
- If the image visually displays text from the caption, or depicts the exact subject the caption describes,
  it is a strong match regardless of CLIP score — score low (0-20).
- CLIP score < 0.22 is only suspicious if the image content ALSO does not match the caption.
- Official news graphics, broadcast overlays, and announcement cards naturally score 0.18-0.24 on CLIP
  due to text overlays. This is expected and not suspicious.
- Look for specific mismatches: wrong person, wrong location, wrong event, wrong time period.
  If you cannot name a concrete mismatch based on what you SEE in the image, do not score high.
- Your PRIMARY evidence is what you can directly observe in the image vs. the caption.
  Reverse image search findings are secondary — they can be wrong. Base caption-image alignment
  assessment on the visual content, not on what a search engine claims the image is from.

CRITICAL — do not blindly inherit the reverse image search narrative:
- If the reverse image search claims the image is from country X but the image itself contains
  visual cues consistent with country Y (signage, flags, uniforms, landscape), trust your
  visual analysis over the search result.
- A score above 80 is only warranted if you can directly observe a clear mismatch between
  what the image shows and what the caption claims — not just because a search engine found
  a similar image elsewhere. Reverse image search alone caps your score at 70.

Return ONLY valid JSON, no markdown fences:
{"score": <integer 0-100>, "assessment": "<2-3 sentences focusing on semantic caption-image alignment>"}
"""

_SYNTHESIZER_SYSTEM = """\
You are the chief analyst of a forensic council that has just reached a verdict on a social media post.
Three specialists submitted scores and assessments. Your job is to identify the 3 strongest reasons
that explain the council's verdict — concrete, evidence-grounded, and distinct from one another.

Rules:
- Each reason must cite a specific signal: a score, p-value, date, source, or visual observation.
- Do not merely restate the verdict or say "the council decided X."
- Keep each reason to 1–2 sentences.
- Order from strongest to weakest evidence.

Return ONLY valid JSON, no markdown fences:
{"top_reasons": ["<reason 1>", "<reason 2>", "<reason 3>"]}
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_parse(raw: str) -> dict:
    try:
        data  = json.loads(raw)
        score = max(0, min(100, int(data.get("score", _FALLBACK_SCORE))))
        return {"score": score, "assessment": str(data.get("assessment", ""))}
    except Exception:
        return {"score": _FALLBACK_SCORE, "assessment": "(parse error)"}


def _fetch_image_bytes(image_url: str) -> tuple:
    """Download image once; return (bytes, mime_type) or (None, '')."""
    try:
        resp = requests.get(image_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        ext  = image_url.split("?")[0].rsplit(".", 1)[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png",  "webp": "image/webp"}.get(ext, "image/jpeg")
        return resp.content, mime
    except Exception:
        return None, ""


def _build_full_context(
    caption: str,
    stats: dict,
    reverse_search: dict | None,
    caption_image_similarity: float | None,
) -> str:
    rs   = reverse_search or {}
    ea   = rs.get("earliest_appearance") or {}
    apps = rs.get("all_appearances", [])
    return (
        f"Caption: {caption or '(none)'}\n\n"
        f"Statistical anomaly detection:\n"
        f"  is_anomaly: {stats.get('is_anomaly')}\n"
        f"  p_value: {stats.get('p_value')}  "
        f"(NOTE: p close to 1.0 = image FITS context = not suspicious)\n"
        f"  mahalanobis_distance: {stats.get('mahalanobis_distance')}\n"
        f"  pca_components_used: {stats.get('pca_components_used')}\n"
        f"  outliers_removed_by_mad: {stats.get('outliers_removed_by_mad')}\n\n"
        f"CLIP caption-image similarity: {caption_image_similarity}  "
        f"(>=0.28 = strong; 0.18-0.24 = normal for news graphics; <0.18 = weak)\n\n"
        f"Reverse image search:\n"
        f"  Earliest known date:   {ea.get('date', 'Not found')}\n"
        f"  Earliest source name:  {ea.get('source_name', 'N/A')}\n"
        f"  Earliest page title:   {ea.get('title', 'N/A')}\n"
        f"  Earliest URL:          {ea.get('url', 'N/A')}\n"
        f"  Total web appearances: {len(apps)}\n"
        f"  Search confidence:     {rs.get('search_confidence', 'N/A')}\n"
    )


def _call_persona(contents, system_prompt: str, temperature: float) -> dict:
    """Single reusable caller — used for all 3 personas with pre-built contents."""
    from google.genai import types as genai_types
    client = _get_client()
    resp   = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=temperature,
        ),
    )
    return _safe_parse(resp.text)


def _aggregate(scores: dict) -> dict:
    mean_score = sum(scores.values()) / len(scores)
    if mean_score >= _SCORE_VERIFIED:
        verdict, label = "VERIFIED MISINFORMATION", "🚨 VERIFIED MISINFORMATION"
    elif mean_score >= _SCORE_LIKELY:
        verdict, label = "LIKELY MISINFORMATION",   "⚠️ LIKELY MISINFORMATION"
    elif mean_score >= _SCORE_UNCERTAIN:
        verdict, label = "N/A",                     "🔍 UNCERTAIN"
    else:
        verdict, label = "LIKELY TRUE",             "✅ LIKELY TRUE"
    return {
        "forensic_verdict": verdict,
        "gemini_label":     label,
        "council_mean_score": round(mean_score, 1),
    }


def _build_reasoning(scores: dict, assessments: dict) -> str:
    parts = [
        f"[{name.replace('_', ' ').title()}, score {score}] {assessments.get(name, '')}"
        for name, score in scores.items()
    ]
    words = " ".join(parts).split()
    return " ".join(words[:150])


def _run_top_reasons(scores: dict, assessments: dict, verdict: str, context_text: str) -> list:
    """Ask the council synthesizer for the 3 strongest reasons behind the verdict."""
    from google.genai import types as genai_types
    persona_summary = "\n".join(
        f"- {name.replace('_', ' ').title()} (score {score}/100): {assessments.get(name, '')}"
        for name, score in scores.items()
    )
    prompt = (
        f"Verdict: {verdict}\n"
        f"Council mean score: {round(sum(scores.values()) / len(scores), 1)}/100\n\n"
        f"Persona assessments:\n{persona_summary}\n\n"
        f"Full signal context:\n{context_text}"
    )
    try:
        client = _get_client()
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=_SYNTHESIZER_SYSTEM,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        data = json.loads(resp.text)
        reasons = data.get("top_reasons", [])
        if isinstance(reasons, list) and reasons:
            return [str(r) for r in reasons[:3]]
    except Exception as e:
        print(f"[council] synthesizer failed: {e}")
    return []


def _build_neutral_fallback(reason: str) -> dict:
    neutral = {"statistical_cynic": _FALLBACK_SCORE, "historian": _FALLBACK_SCORE, "linguist": _FALLBACK_SCORE}
    return {
        "gemini_label": "❓ UNKNOWN", "gemini_confidence": 0,
        "gemini_explanation": f"Council unavailable: {reason}",
        "forensic_verdict": "N/A", "forensic_reasoning": f"Council unavailable: {reason}",
        "council_veto_triggered": False, "council_veto_persona": None,
        "council_scores": neutral, "council_mean_score": float(_FALLBACK_SCORE),
        "top_reasons": [],
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
    if simulation_mode:
        return _SIMULATION_RESULT.copy()

    if not os.getenv("GOOGLE_API_KEY"):
        return _build_neutral_fallback("No GOOGLE_API_KEY set")

    # Download image once — the bytes are reused across all 3 concurrent calls
    image_bytes, mime_type = _fetch_image_bytes(image_url) if image_url else (None, "")

    # Build the combined context message once
    text_msg = _build_full_context(caption, stats, reverse_search, caption_image_similarity)

    # Assemble contents once (multimodal if image available, text-only fallback)
    from google.genai import types as genai_types
    if image_bytes:
        contents = [
            genai_types.Part(inline_data=genai_types.Blob(data=image_bytes, mime_type=mime_type)),
            genai_types.Part(text=text_msg),
        ]
    else:
        contents = text_msg

    persona_configs = {
        "statistical_cynic": (_CYNIC_SYSTEM,    0.0),
        "historian":         (_HISTORIAN_SYSTEM, 0.3),
        "linguist":          (_LINGUIST_SYSTEM,  0.3),
    }

    scores      = {}
    assessments = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            name: executor.submit(_call_persona, contents, sys_prompt, temp)
            for name, (sys_prompt, temp) in persona_configs.items()
        }
        for name, future in futures.items():
            try:
                result            = future.result(timeout=_PERSONA_TIMEOUT)
                scores[name]      = max(0, min(100, int(result.get("score", _FALLBACK_SCORE))))
                assessments[name] = str(result.get("assessment", ""))
                print(f"[council] {name}: score={scores[name]}")
            except FuturesTimeoutError:
                print(f"[council] {name} timed out")
                scores[name]      = _FALLBACK_SCORE
                assessments[name] = f"({name} timed out)"
            except Exception as e:
                print(f"[council] {name} failed: {e}")
                scores[name]      = _FALLBACK_SCORE
                assessments[name] = f"({name} unavailable)"

    agg = _aggregate(scores)

    top_reasons = _run_top_reasons(scores, assessments, agg["forensic_verdict"], text_msg)
    print(f"[council] top_reasons: {top_reasons}")

    return {
        "gemini_label":           agg["gemini_label"],
        "gemini_confidence":      int(round(agg["council_mean_score"])),
        "gemini_explanation":     max(assessments.values(), key=len, default="Council analysis inconclusive."),
        "forensic_verdict":       agg["forensic_verdict"],
        "forensic_reasoning":     _build_reasoning(scores, assessments),
        "council_veto_triggered": False,
        "council_veto_persona":   None,
        "council_scores":         scores,
        "council_mean_score":     agg["council_mean_score"],
        "top_reasons":            top_reasons,
    }
