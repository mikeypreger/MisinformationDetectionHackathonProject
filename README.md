# Miss Information
### Out-of-Context Image Detection — HUJI Hackathon 2026
*"Trust & Safety in the AI Era: Detecting Fakes"*

Built at HUJI Hackathon 2026 ("Trust & Safety in the AI Era: Detecting Fakes),
where it placed **5th**.

- Itamar Galpern
- Mikey Preger
- Adi Ozana
- Yair Israel
---

## What is Miss Information?

Miss Information detects **cheapfakes** — real, unedited photos attached to the wrong event, time, or place.

Paste a social media post URL. The system tells you whether the image actually matches the caption, with a cited, human-readable verdict.

> Most detection tools fail on the hardest case: a 100% authentic photo from 2016 reused to illustrate a 2024 event. The pixels are real. The caption is a lie. Only **provenance** — tracing where and when the image *first* appeared — can catch this.

---

## The Two Failure Modes We Catch

| Type | Description | How we catch it |
|---|---|---|
| **Contextual transplant** | Real photo, wrong event / date / place | Reverse image search + provenance dating (Historian persona) |
| **Caption mismatch** | The caption describes something the image doesn't show | CLIP image–caption friction score + Linguist persona |

---

## Architecture

```
Input: social media post URL
          │
          ▼
┌──────────────────────────────────────────┐
│  Stage 1 — Scrape                        │
│  BrightData (IG / FB / X / TikTok)       │
│  Reddit native API                       │
│  → image URL + caption                   │
└──────────────────┬───────────────────────┘
                   │
          ┌────────┴────────┐
          ▼                 ▼                  ▼
  Gemini queries    Google Lens          EXIF metadata
  (caption →        reverse search      (piexif)
  search terms)     (SerpAPI)
          │                 │                  │
          └────────┬────────┘                  │
                   ▼                           │
┌──────────────────────────────────────────┐  │
│  Stage 3 — Context pool                  │  │
│  BrightData Google Images Light          │  │
│  up to 60 images fetched in parallel     │  │
└──────────────────┬───────────────────────┘  │
                   │◄──────────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  Stage 4 — Embedding + Anomaly           │
│  DINOv2 ViT-B/14 — context embeddings    │
│  Mahalanobis distance + PCA              │
│  CLIP ViT-B/32 — caption↔image sim.      │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  Stage 5 — Council                       │
│  3 × Gemini 2.5 Flash personas           │
│    Statistical Cynic  (anomaly math)     │
│    Historian          (temporal provenance)│
│    Linguist           (caption logic)    │
│  Averaged score → verdict label          │
└──────────────────┬───────────────────────┘
                   ▼
            Verdict + Report
```

All of Stage 2 (Gemini queries, Google Lens, EXIF) runs in parallel via `ThreadPoolExecutor`. All three Council personas also fire concurrently.

---

## Verdict Labels

| Score | Label |
|---|---|
| ≥ 65 | **VERIFIED MISINFORMATION** |
| ≥ 45 | **LIKELY MISINFORMATION** |
| ≥ 25 | **UNCERTAIN** |
| < 25 | **LIKELY AUTHENTIC** |

Each verdict comes with a 2–3 sentence explanation, the earliest known image appearance with a source link, and per-persona score breakdown.

---

## Tech Stack

| Component | Technology |
|---|---|
| Social media scraping | BrightData Dataset API (Instagram, Facebook, Twitter/X, TikTok) |
| Reddit scraping | Reddit JSON API (native, no key required) |
| Reverse image search | SerpAPI Google Lens (`exact_matches` → `visual_matches` fallback) |
| Context image pool | BrightData Google Images Light |
| Search query generation | Gemini 2.5 Flash |
| Visual embeddings | DINOv2 ViT-B/14 (`torch.hub`) |
| Caption–image similarity | CLIP ViT-B/32 (`open_clip`) |
| Anomaly detection | Mahalanobis distance + PCA (`scikit-learn`, `scipy`) |
| EXIF metadata | `piexif` |
| Page date extraction | BeautifulSoup (`lxml`) with 3s timeout, run in parallel |
| Council personas | Gemini 2.5 Flash × 3 (temperature 0 for Historian) |
| Backend | FastAPI + uvicorn |
| Frontend | React + Tailwind CSS + Vite |

---

## Project Structure

```
MisinformationDetectionHackathonProject/
├── server.py                  # FastAPI backend + React SPA host
├── MyApp.py                   # Pipeline orchestrator (+ Streamlit debug UI)
├── requirements.txt
├── .env                       # API keys (not committed)
│
├── pipeline/
│   ├── url_normalizer.py      # URL normalization + platform detection
│   ├── social_scraper.py      # BrightData + Reddit scraping
│   ├── data_parser.py         # Per-platform image URL extraction
│   ├── caption_extractor.py   # Gemini → search queries
│   ├── context_enricher.py    # Google Lens reverse search + date extraction
│   ├── image_fetcher.py       # BrightData Google Images + parallel download
│   ├── embedder.py            # DINOv2 + CLIP embedding
│   ├── anomaly_detector.py    # Mahalanobis distance + PCA anomaly scoring
│   ├── image_guardrail.py     # Pre-flight image quality check
│   ├── council.py             # 3-persona Gemini council + verdict aggregation
│   └── utils_network.py       # Shared HTTP fetch with proxy + UA rotation
│
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── Hero.jsx        # URL input form + loading state
    │   │   ├── LoadingTips.jsx # Rotating misinformation tips carousel
    │   │   └── ResultCard.jsx  # Verdict display
    │   └── App.jsx
    └── dist/                  # Built by `npm run build`, served by FastAPI
```

---

## Setup

### 1. Clone & install Python dependencies

```bash
git clone <repo-url>
cd MisinformationDetectionHackathonProject

pip install -r requirements.txt

# Download spaCy English model
python -m spacy download en_core_web_sm
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
# BrightData
BRIGHT_DATA_TOKEN=your_token
ID_INSTAGRAM=your_scraper_id
ID_FACEBOOK=your_scraper_id
ID_TWITTER=your_scraper_id
ID_TIKTOK=your_scraper_id
ID_REDDIT=your_scraper_id
ID_GOOGLE_IMAGES=your_scraper_id

# BrightData residential proxy (for direct page fetches)
BRD_PROXY_HOST=brd.superproxy.io
BRD_PROXY_PORT=33335
BRD_PROXY_USER=your_user
BRD_PROXY_PASS=your_pass

# SerpAPI (Google Lens reverse search)
SERPAPI_KEY=your_key

# Google Gemini (council + query generation)
GOOGLE_API_KEY=your_key

# Set to False to run the FastAPI server (production)
# Set to True to run the Streamlit debug UI
DEV_MODE=False
```

### 3. Build the frontend

```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Run

**Production (FastAPI + built React SPA):**
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000`.

**Development (hot-reload):**
```bash
# Terminal 1 — backend
uvicorn server:app --port 8000 --reload

# Terminal 2 — frontend dev server
cd frontend
npm run dev
```

**Streamlit debug UI (pipeline introspection):**
```bash
# Set DEV_MODE=True in .env, then:
streamlit run MyApp.py
```

---

## Supported Platforms

Instagram · Twitter / X · Facebook · TikTok · Reddit

---

## Design Principles

**Provenance-first.** Reverse image search is the spine of the pipeline. The Historian persona scores 0–100 purely on temporal mismatch between when the image first appeared and what the caption claims. Everything else is corroborating signal.

**Parallel by default.** Gemini query generation, Google Lens reverse search, and EXIF extraction all fire concurrently. The three Council personas also run in parallel. Total pipeline time is bounded by the slowest single call, not their sum.

**LLMs reason over evidence, not memory.** Every Council persona receives the full structured evidence object — dates, domains, caption, anomaly stats — and reasons over it explicitly. No persona is allowed to substitute training-data recall for cited evidence (enforced via system prompt).

**Visual fallback chain.** Google Lens returns `exact_matches` when it finds the identical image elsewhere; it returns `visual_matches` when it finds only visually similar images. Both signals are useful — exact matches confirm identical pixel provenance, visual matches reveal recycled subject matter. We use `exact_matches` when available and fall back to `visual_matches[:10]` otherwise.

---

## Team

Built at HUJI Hackathon 2026.
