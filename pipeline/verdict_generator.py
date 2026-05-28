import json
import os
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

load_dotenv()

_client = None

_SYSTEM = """\
You are a misinformation detection expert reviewing a social media post.
You are given the post image, its caption, and automated detection statistics.

Classify the post using EXACTLY ONE of these labels:
- "✅ LIKELY REAL" — image authentically represents what the caption claims
- "🔍 AMBIGUOUS" — signals are mixed; cannot determine with confidence
- "🚨 POSSIBLE CHEAPFAKE" — image is used out of context or caption is misleading
- "⚠️ VISUAL ANOMALY" — image appears digitally manipulated or structurally inconsistent
- "❓ UNKNOWN" — insufficient information to classify

Key reasoning rules:
- Official team/organization announcement graphics (e.g. player signings, award posts) naturally
  score LOW on caption-image similarity (< 0.23 CLIP score). Do NOT flag as cheapfake solely on
  this score. Ask: does the image CONTENT match the CLAIM in the caption?
- caption_image_similarity is a CLIP cosine score. Real news photos score 0.25-0.40; styled
  graphics and team announcement visuals score 0.15-0.22 even when perfectly authentic.
- Only flag POSSIBLE CHEAPFAKE if the image visibly shows something different from what the
  caption describes (wrong person, wrong location, wrong event, wrong time period).
- p_value close to 1.0 means the image fits the visual context cluster — not suspicious alone.
- Use VISUAL ANOMALY only when the image appears digitally manipulated.

Also provide:
- confidence: integer 0-100 expressing how certain you are of your classification
- explanation: one sentence explaining your reasoning

Return JSON only:
{"label": "<one of the 5 labels above>", "confidence": <0-100>, "explanation": "<one sentence>"}
"""

_LEVEL_MAP = {
    "✅": "success",
    "🔍": "info",
    "🚨": "error",
    "⚠️": "error",
    "❓": "warning",
}

_FALLBACK_SIM_STRONG = 0.28
_FALLBACK_SIM_WEAK   = 0.23


def _fallback_verdict(is_anomaly, caption_sim) -> tuple[str, str, str, int]:
    if is_anomaly is None:
        return "warning", "⚠️ Inconclusive — not enough context images", "", 0
    if is_anomaly:
        return "error", "⚠️ VISUAL ANOMALY — image is unusual for this topic", "", 50
    if caption_sim is None:
        return "success", "✅ LIKELY REAL", "Image is visually similar to context cluster.", 70
    if caption_sim > _FALLBACK_SIM_STRONG:
        return "success", "✅ LIKELY REAL", "Image matches context and caption description.", 85
    if caption_sim < _FALLBACK_SIM_WEAK:
        return "error", "🚨 POSSIBLE CHEAPFAKE", "Caption-image similarity is low.", 60
    return "info", "🔍 AMBIGUOUS", "Caption-image consistency is unclear.", 50


def generate_verdict(
    caption: str,
    image_url: str,
    is_anomaly,
    p_value: float | None,
    mahalanobis_distance: float | None,
    caption_image_similarity: float | None,
) -> tuple[str, str, str, int]:
    """
    Returns (streamlit_level, label, explanation, confidence 0-100).
    Falls back to threshold logic if Gemini is unavailable.
    """
    global _client
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return _fallback_verdict(is_anomaly, caption_image_similarity)

    try:
        if _client is None:
            _client = genai.Client(api_key=api_key)

        resp = requests.get(image_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        image_bytes = resp.content

        ext = image_url.split("?")[0].rsplit(".", 1)[-1].lower()
        mime_type = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png",  "webp": "image/webp",
        }.get(ext, "image/jpeg")

        stats_text = (
            f"Caption: {caption}\n\n"
            f"Detection stats:\n"
            f"- is_anomaly: {is_anomaly}\n"
            f"- p_value: {p_value}\n"
            f"- mahalanobis_distance: {mahalanobis_distance}\n"
            f"- caption_image_similarity (CLIP cosine): {caption_image_similarity}\n"
        )

        contents = [
            genai_types.Part(
                inline_data=genai_types.Blob(data=image_bytes, mime_type=mime_type)
            ),
            genai_types.Part(text=stats_text),
        ]

        result = _client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=_SYSTEM,
                response_mime_type="application/json",
                temperature=0,
            ),
        )

        data = json.loads(result.text)
        label       = str(data.get("label", "❓ UNKNOWN"))
        explanation = str(data.get("explanation", ""))
        confidence  = max(0, min(100, int(data.get("confidence", 50))))

        level = "warning"
        for emoji, lvl in _LEVEL_MAP.items():
            if label.startswith(emoji):
                level = lvl
                break

        print(f"[verdict_generator] {label} (confidence={confidence}%)")
        return level, label, explanation, confidence

    except Exception as e:
        print(f"[verdict_generator] Gemini failed, using fallback: {e}")
        return _fallback_verdict(is_anomaly, caption_image_similarity)
