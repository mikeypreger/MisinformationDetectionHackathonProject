# AstroDetect 🔍
### Out-of-Context Image Detection — HUJI Hackathon 2026
*"Trust & Safety in the AI Era: Detecting Fakes"*

---

## What is AstroDetect?

AstroDetect detects **cheapfakes** — real, unedited photos attached to the wrong event, time, or place.

You submit a social media post (image + caption). AstroDetect tells you whether the image actually supports the caption, with a cited, human-readable report.

> Most detection tools fail on the hardest case: a 100% real photo from 2019 reused to illustrate a 2024 event. The pixels are authentic. The caption is a lie. Only provenance — tracing where and when the image *actually* first appeared — can catch this. That's what we're built around.

---

## The Two Failure Modes We Catch

| Type | Description | How we catch it |
|---|---|---|
| **Pixel-level mismatch** | The caption describes something the image doesn't show | CLIP friction score + LLM visual analysis |
| **Contextual transplant** | Real photo, wrong event/date/place (the real cheapfake) | Reverse image search + provenance dating |

---

## Pipeline Architecture

```
Input: image + caption
        │
        ▼
┌─────────────────────────────────────┐
│  Stage 1 — Reverse Image Search     │  ← the spine
│  Find earliest known appearance     │
│  Extract date + original context    │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Stage 2 — Cheap Signals            │  ← weak priors only
│  EXIF / C2PA metadata check         │
│  CLIP image–caption friction score  │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Stage 3 — Distance Analysis        │
│  Query vs. earliest original (strong│
│  → manipulation heatmap             │
│  Query vs. verified corpus (weak)   │
│  → outlier score                    │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Stage 4 — LLM Panel                │  ← adjudication, last
│  ≥3 independent judges              │
│  (Claude + Gemini, odd-number vote) │
│  Majority vote + Cohen's κ          │
└─────────────────┬───────────────────┘
                  │
                  ▼
Output: Verdict Report
```

---

## Output Report

Every analysis produces:

- **Verdict badge:** `Match` / `Misleading context` / `Manipulated-flag` / `Unverifiable`
- **Confidence score** based on inter-judge agreement (Cohen's κ)
- **3–4 sentence explanation** of what diverges between image and caption
- **Earliest known appearance** with a citation link — this is the evidence a user can verify themselves
- **Per-claim breakdown:** `SUPPORTED` / `REFUTED` / `NOT-ENOUGH-INFO`
- **Manipulation heatmap** highlighting edited regions (when applicable)

---

## Tech Stack

| Component | Technology |
|---|---|
| Reverse image search | SerpApi Google Lens / Google Cloud Vision |
| Visual embeddings | CLIP via `open_clip` |
| Metadata | `piexif` + `c2pa-python` |
| Distance / outlier | `sklearn` kNN + cosine similarity |
| Heatmap | Query vs. original diff |
| LLM judges | Claude API + Gemini API |
| UI | Streamlit |
| Benchmark / calibration | COSMOS dataset (arXiv 2101.06278) |

---

## Design Principles

**Provenance-first.** Reverse image search is the spine of the pipeline. Every other signal is either a corroborator or a prior — never the verdict.

**Cheap signals are weak priors, not verdicts.** EXIF metadata, CLIP friction, and AI-generation detection can raise suspicion. They can never clear an image. A false "VERIFIED" is our worst possible outcome.

**LLMs adjudicate evidence, they don't recall facts.** Every judge in our panel receives the structured evidence object and reasons over it. This is our main hallucination defense.

**Calibration over formulas.** Every numeric threshold is calibrated on the COSMOS benchmark with ROC curves. A calibration plot is more honest — and more convincing to a technical audience — than a Greek-letter formula.

---

## What We Deliberately Did Not Build

| Cut feature | Why |
|---|---|
| FID / Fréchet distance | Undefined for single-image-vs-set; use kNN/cosine instead |
| Cross-platform coordination DAG | Different problem; timestamp data unreliable |
| AI-generation as a verdict | Detection is unreliable under compression; flag only |
| Magic thresholds | Everything calibrated on benchmark data |

---

## Team

Built at HUJI Hackathon 2026 by:

- **[Name]** — pipeline orchestration, distance math, calibration, Streamlit
- **[Name]** — image understanding + claim decomposition prompts
- **[Name]** — LLM panel design, voting aggregation, report generation
- **[Name]** — benchmark curation, verified corpus harvesting

---

## Setup

```bash
# Clone the repo
git clone https://github.com/your-username/astrodetect.git
cd astrodetect

# Install dependencies
py -m pip install -r requirements.txt

# Add your API keys
cp .env.example .env
# then fill in: SERPAPI_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY

# Run
streamlit run app.py
```

---

## References

- COSMOS — *Catching Out-of-Context Misinformation with Self-Supervised Learning* ([arXiv 2101.06278](https://arxiv.org/abs/2101.06278))
- MMSys'21 / ICME'23 Detecting Cheapfakes grand-challenge papers
- TruFor — image forgery detection + localization heatmap ([arXiv 2212.10957](https://arxiv.org/abs/2212.10957))
- C2PA / Content Credentials specification
- CLEF CheckThat! 2025 ([arXiv 2503.14828](https://arxiv.org/abs/2503.14828))

---

*The name "AstroDetect" is a working title from an earlier iteration of the project.*