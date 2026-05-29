"""
server.py  —  FastAPI backend + React SPA host for Miss Information.

Run (production):
    uvicorn server:app --host 0.0.0.0 --port 8000

Run (development — pair with `cd FRONTEND && npm run dev`):
    uvicorn server:app --port 8000 --reload
"""

import json
import os
import time

# Must be set before MyApp is imported so Streamlit is never loaded.
os.environ.setdefault("DEV_MODE", "False")

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from MyApp import run_pipeline

app = FastAPI(title="Miss Information API", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

_DIST = os.path.join(os.path.dirname(__file__), "FRONTEND", "dist")

# ── Gemini synthesis ──────────────────────────────────────────────────────────
# Takes the rich pipeline output and produces clean, user-facing UI copy for
# the React ResultCard. Runs multimodal (image + JSON) so imageAlt is accurate.

_SYNTH_SYSTEM = """\
You are a UX writer for "Miss Information," a visual misinformation detection tool.
You receive structured JSON output from a forensic analysis pipeline. Your job is to
produce concise, accurate copy for the results panel shown to the end user.

Rules:
- verdict:  ONE sentence (≤ 20 words), plain English, no emoji, present tense
- analysis: 2–3 sentences explaining what the evidence shows and why this risk level was assigned
- imageAlt: brief accessibility label for the photograph (start with "Photo showing …")
- signals:  3–5 short strings (≤ 12 words each) citing concrete evidence from the data

Return ONLY valid JSON, no markdown fences:
{"verdict": str, "analysis": str, "imageAlt": str, "signals": [str]}
"""


def _gemini_synthesize(pipeline_result: dict) -> dict | None:
    """Call Gemini 2.5 Flash (multimodal) to generate frontend copy from pipeline output."""
    try:
        from google import genai
        from google.genai import types as genai_types
        import requests as _req

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None

        client = genai.Client(api_key=api_key)

        summary = {k: pipeline_result.get(k) for k in (
            "forensic_verdict", "forensic_reasoning",
            "gemini_label", "gemini_confidence", "gemini_explanation",
            "council_scores", "council_mean_score",
            "council_veto_triggered", "council_veto_persona",
            "is_anomaly", "p_value", "mahalanobis_distance",
            "caption_image_similarity", "caption",
            "reverse_image_search",
        )}
        text_part = f"Pipeline result:\n{json.dumps(summary, indent=2)}"

        # Include the post image so Gemini can write an accurate imageAlt and
        # visually-grounded analysis copy.
        image_url = pipeline_result.get("image_url", "")
        contents: list = [text_part]
        if image_url:
            try:
                img_resp = _req.get(image_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                img_resp.raise_for_status()
                ext  = image_url.split("?")[0].rsplit(".", 1)[-1].lower()
                mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                        "png": "image/png",  "webp": "image/webp"}.get(ext, "image/jpeg")
                contents = [
                    genai_types.Part(inline_data=genai_types.Blob(data=img_resp.content, mime_type=mime)),
                    genai_types.Part(text=text_part),
                ]
            except Exception:
                pass  # fall back to text-only; still works fine

        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=_SYNTH_SYSTEM,
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        return json.loads(resp.text)
    except Exception as e:
        print(f"[server] Gemini synthesis failed: {e}")
        return None


# ── Mapping helpers ───────────────────────────────────────────────────────────

def _context_risk(verdict: str, confidence: int) -> str:
    if verdict in ("VERIFIED MISINFORMATION", "LIKELY MISINFORMATION"):
        return "High" if confidence >= 65 else "Medium"
    if verdict == "LIKELY TRUE":
        return "Low"
    return "Medium"


def _fallback_copy(result: dict) -> dict:
    return {
        "verdict":  result.get("gemini_explanation") or f"Verdict: {result.get('forensic_verdict', 'N/A')}",
        "analysis": result.get("forensic_reasoning") or "No detailed reasoning available.",
        "imageAlt": "Image extracted from social media post",
        "signals":  _fallback_signals(result),
    }


def _fallback_signals(result: dict) -> list:
    signals = []
    if result.get("council_veto_triggered"):
        who = (result.get("council_veto_persona") or "").replace("_", " ").title()
        signals.append(f"Hard veto triggered by {who}")
    for name, score in (result.get("council_scores") or {}).items():
        if score >= 65:
            signals.append(f"{name.replace('_', ' ').title()} flagged ({score}/100)")
    if result.get("is_anomaly"):
        p = result.get("p_value")
        signals.append(f"Statistical outlier detected (p={p:.4f})" if p else "Statistical outlier detected")
    ea = (result.get("reverse_image_search") or {}).get("earliest_appearance") or {}
    if ea.get("date"):
        signals.append(f"Earliest image sighting: {ea['date']}")
    sim = result.get("caption_image_similarity")
    if sim is not None and sim < 0.22:
        signals.append(f"Low caption–image alignment ({sim:.2f})")
    return signals[:5] or ["No specific signals detected"]



# ── Request model ─────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    url: str
    simulation_mode: bool = False


# ── API endpoint ──────────────────────────────────────────────────────────────

@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    t0     = time.time()
    result = run_pipeline(req.url, simulation_mode=req.simulation_mode)
    elapsed = round(time.time() - t0, 1)

    if result.get("error") and not result.get("gemini_label"):
        raise HTTPException(status_code=422, detail=result["error"])
    if result.get("guardrail_blocked"):
        raise HTTPException(
            status_code=422,
            detail=result.get("guardrail_reason", "Image failed quality check"),
        )

    verdict    = result.get("forensic_verdict", "N/A")
    confidence = result.get("gemini_confidence") or 0

    # Gemini synthesis runs for full-pipeline results; fallback handles errors / early stages.
    synth = _gemini_synthesize(result) if result.get("pipeline_stage") == 4 else None
    copy  = synth or _fallback_copy(result)

    return {
        "imageUrl":    result.get("image_url", ""),
        "imageAlt":    copy.get("imageAlt", "Image extracted from social media post"),
        "contextRisk": _context_risk(verdict, confidence),
        "confidence":  confidence,
        "verdict":     copy.get("verdict", ""),
        "analysis":    copy.get("analysis", ""),
        "signals":     copy.get("signals", []),
        "topReasons":  result.get("top_reasons", []),
        "metadata": {
            "platform":        (result.get("platform") or "Unknown").replace("_", " ").title(),
            "analysisTime":    f"{elapsed}s",
            "imageResolution": "N/A",
            "sourceVerified":  verdict == "LIKELY TRUE",
        },
    }


# ── Serve React SPA (production build) ───────────────────────────────────────
# API routes above always win; StaticFiles catches everything else.

if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="spa")
