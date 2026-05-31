"""
MyApp.py  —  Miss Information
"""

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

DEV_MODE       = os.getenv("DEV_MODE", "True").lower() == "true"
PIPELINE_STAGE = int(os.getenv("PIPELINE_STAGE", "4"))

from pipeline.url_normalizer    import normalize_url
from pipeline.social_scraper    import scrape_post, fetch_reddit_data
from pipeline.caption_extractor import extract_search_queries
from pipeline.image_fetcher     import fetch_context_image_urls, download_images_parallel
from pipeline.embedder          import (
    load_clip_model, embed_images, embed_single_image,
    embed_text, load_image_from_url,
)
from pipeline.anomaly_detector  import run_anomaly_detection
from pipeline.image_guardrail   import check_image_quality
from pipeline.context_enricher  import run_reverse_image_search, extract_image_metadata
from pipeline.council import (
    run_council,
    _SIM_CONTEXT_EMBEDDINGS,
    _SIM_QUERY_EMBEDDING,
    _SIM_CAPTION_SIM,
)

if DEV_MODE:
    import streamlit as st

def run_pipeline(
    input_url: str,
    stage: int = PIPELINE_STAGE,
    embedding_model: str = "dino",
    use_gmm: bool = False,
    simulation_mode: bool = False,
) -> dict:
    """Full pipeline — DINOv2 ViT-B/14 for anomaly detection, CLIP for caption similarity."""

    # ── Stage 1: Normalize URL + scrape post ─────────────────────────────────
    try:
        normalized_url, platform_key = normalize_url(input_url)
    except ValueError as e:
        return {"error": str(e), "input_url": input_url}

    post_date = None
    if platform_key == "reddit":
        image_url, caption, post_date = fetch_reddit_data(normalized_url)
        caption = caption or ""
    else:
        post_data = scrape_post(normalized_url, platform_key)
        image_url = post_data.get("image_url")
        caption   = post_data.get("caption", "")

    if not image_url:
        return {
            "error": "Could not extract image from post",
            "input_url": input_url,
            "normalized_url": normalized_url,
            "caption": caption,
            "pipeline_stage": stage,
        }

    if stage == 1:
        return {
            "input_url": input_url,
            "normalized_url": normalized_url,
            "platform": platform_key,
            "image_url": image_url,
            "caption": caption,
            "pipeline_stage": 1,
        }

    # ── Phase 0: Visual Guardrail — download query image early ───────────────
    # Download now so we can check quality before the expensive context-pool build.
    try:
        query_pil = load_image_from_url(image_url)
    except Exception as e:
        return {
            "error": f"Failed to download post image: {e}",
            "image_url": image_url,
            "caption": caption,
            "pipeline_stage": stage,
        }

    is_viable, guardrail_reason = check_image_quality(query_pil)
    if not is_viable:
        return {
            "guardrail_blocked": True,
            "guardrail_reason": guardrail_reason,
            "input_url": input_url,
            "normalized_url": normalized_url,
            "platform": platform_key,
            "image_url": image_url,
            "caption": caption,
            "pipeline_stage": 0,
        }

    # ── Stages 2 + 2.5: fire all three independent network calls concurrently ────
    # extract_search_queries (Gemini), run_reverse_image_search (SerpAPI Lens), and
    # extract_image_metadata (EXIF) share no data dependencies — run in parallel.
    from concurrent.futures import ThreadPoolExecutor as _TPE

    with _TPE(max_workers=3) as _ex:
        _fq = _ex.submit(extract_search_queries, caption, normalized_url)
        _fr = _ex.submit(run_reverse_image_search, image_url)
        _fm = _ex.submit(extract_image_metadata, image_url)
        queries        = _fq.result()
        reverse_search = _fr.result()
        image_metadata = _fm.result()

    if stage == 2:
        return {
            "input_url": input_url,
            "normalized_url": normalized_url,
            "platform": platform_key,
            "image_url": image_url,
            "caption": caption,
            "search_queries": queries,
            "pipeline_stage": 2,
        }

<<<<<<< HEAD
    # Reddit post date: use as earliest_appearance fallback when Lens finds nothing
    if post_date and reverse_search and reverse_search.get("earliest_appearance") is None:
        reverse_search["earliest_appearance"] = {
            "date":        post_date,
            "source_name": "Reddit (original post)",
            "url":         normalized_url,
            "title":       caption[:80] if caption else "",
            "match_type":  "reddit_post",
            "context":     "",
        }

    # ── Stage 3: Fetch context image URLs ────────────────────────────────────
    context_urls = fetch_context_image_urls(queries, max_total=60)
=======
    # ── Phase 2.5 + Stage 3 in parallel ─────────────────────────────────────────
    # Reverse search and EXIF fire in background threads while context URLs are
    # fetched on the main thread — all three are independent network calls.
    from concurrent.futures import ThreadPoolExecutor as _Pool
    with _Pool(max_workers=2) as _pool:
        _fr = _pool.submit(run_reverse_image_search, image_url)
        _fm = _pool.submit(extract_image_metadata,   image_url)
        context_urls = fetch_context_image_urls(queries, max_total=60)
        try:
            reverse_search = _fr.result(timeout=20)
        except Exception as _e:
            print(f"[pipeline] reverse search failed: {_e}"); reverse_search = {}
        try:
            image_metadata = _fm.result(timeout=20)
        except Exception as _e:
            print(f"[pipeline] metadata extraction failed: {_e}"); image_metadata = {}
>>>>>>> f394ba5a9159d4337921ef96ac36888ac2c4d583

    if stage == 3:
        return {
            "input_url": input_url,
            "normalized_url": normalized_url,
            "platform": platform_key,
            "image_url": image_url,
            "caption": caption,
            "search_queries": queries,
            "context_images_fetched": len(context_urls),
            "context_image_urls_sample": context_urls[:20],
            "reverse_image_search": reverse_search,
            "image_metadata": image_metadata,
            "pipeline_stage": 3,
        }

    # ── Stage 4: Full pipeline — embed → anomaly + caption score ─────────────
    import numpy as np

    if simulation_mode:
        context_embeddings       = _SIM_CONTEXT_EMBEDDINGS
        query_embedding          = _SIM_QUERY_EMBEDDING
        caption_image_similarity = _SIM_CAPTION_SIM
    else:
        context_pil_images = download_images_parallel(context_urls)
        context_embeddings = embed_images(context_pil_images[:20], model=embedding_model)
        query_embedding    = embed_single_image(query_pil,    model=embedding_model)

        # Caption-image similarity: always CLIP (DINOv2 has no text encoder).
        caption_image_similarity = None
        if caption.strip():
            try:
                load_clip_model()
                clip_query = embed_single_image(query_pil, model="clip")
                cap_emb = embed_text(caption)
                caption_image_similarity = round(float(np.dot(clip_query, cap_emb)), 4)
            except Exception as e:
                print(f"[pipeline] caption-image similarity failed: {e}")

    stats = run_anomaly_detection(
        context_embeddings,
        query_embedding,
        use_gmm=use_gmm,
    )

    # ── Phase 5: Council veto engine ─────────────────────────────────────────
    council_result = run_council(
        caption=caption,
        image_url=image_url,
        stats=stats,
        reverse_search=reverse_search,
        caption_image_similarity=caption_image_similarity,
        simulation_mode=simulation_mode,
    )

    return {
        "input_url": input_url,
        "normalized_url": normalized_url,
        "platform": platform_key,
        "image_url": image_url,
        "caption": caption,
        "search_queries": queries,
        "context_images_fetched": len(context_urls),
        "context_images_embedded": int(context_embeddings.shape[0]),
        "caption_image_similarity": caption_image_similarity,
        "embedding_model": embedding_model,
        "pipeline_stage": 4,
        "reverse_image_search": reverse_search,
        "image_metadata": image_metadata,
        **council_result,
        **stats,
    }


# ── Streamlit UI ──────────────────────────────────────────────────────────────


def _sh(title: str) -> None:
    """Render a styled section header."""
    st.markdown(
        f"""<div style="
            margin: 1.6rem 0 0.6rem;
            padding-bottom: 0.4rem;
            border-bottom: 1px solid #1e2a3a;
        ">
            <span style="
                font-family:'Space Grotesk',sans-serif;
                font-size:1.05rem;
                font-weight:600;
                color:#c8d6e5;
                letter-spacing:0.04em;
                text-transform:uppercase;
            ">{title}</span>
        </div>""",
        unsafe_allow_html=True,
    )


def _render_ui():
    st.set_page_config(
        page_title="MISS INFORMATION",
        page_icon="🔍",
        layout="centered",
        initial_sidebar_state="expanded",
    )

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    #MainMenu, footer { visibility: hidden; }

    .stApp {
        background: linear-gradient(160deg, #06090f 0%, #0d1321 55%, #0a0e1a 100%) !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b0f1e 0%, #0d1321 100%) !important;
        border-right: 1px solid #1c2535 !important;
    }
    [data-testid="stSidebar"] * { color: #c8d6e5 !important; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        font-family: 'Space Grotesk', sans-serif !important;
        color: #e2e8f0 !important;
        letter-spacing: 0.04em !important;
    }

    /* Text input */
    [data-testid="stTextInput"] input {
        background: #111827 !important;
        border: 1.5px solid #2d3748 !important;
        border-radius: 10px !important;
        color: #e2e8f0 !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.95rem !important;
        padding: 0.75rem 1rem !important;
        transition: border-color 0.2s, box-shadow 0.2s !important;
    }
    [data-testid="stTextInput"] input:focus {
        border-color: #e63946 !important;
        box-shadow: 0 0 0 3px rgba(230,57,70,0.18) !important;
        outline: none !important;
    }
    [data-testid="stTextInput"] label {
        color: #8892b0 !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.12em !important;
    }

    /* Primary button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #e63946 0%, #c1121f 100%) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 10px !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        letter-spacing: 0.06em !important;
        padding: 0.6rem 2.2rem !important;
        box-shadow: 0 4px 18px rgba(230,57,70,0.35) !important;
        transition: all 0.2s !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #ff4d5a 0%, #e63946 100%) !important;
        box-shadow: 0 6px 24px rgba(230,57,70,0.5) !important;
        transform: translateY(-2px) !important;
    }
    .stButton > button[kind="primary"]:disabled {
        opacity: 0.55 !important;
        transform: none !important;
    }

    /* Metrics cards */
    [data-testid="metric-container"] {
        background: #111827 !important;
        border: 1px solid #1e2a3a !important;
        border-radius: 12px !important;
        padding: 1rem 1.2rem !important;
    }
    [data-testid="metric-container"] > label {
        color: #8892b0 !important;
        font-size: 0.72rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.12em !important;
        font-weight: 500 !important;
    }
    [data-testid="stMetricValue"] {
        color: #e2e8f0 !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1.5rem !important;
    }

    /* Headings */
    h1, h2, h3 {
        font-family: 'Space Grotesk', sans-serif !important;
        color: #e2e8f0 !important;
        letter-spacing: -0.02em !important;
    }

    /* Expanders */
    [data-testid="stExpander"] summary {
        background: #111827 !important;
        border-radius: 10px !important;
        color: #c8d6e5 !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 500 !important;
    }
    [data-testid="stExpander"] {
        border: 1px solid #1e2a3a !important;
        border-radius: 10px !important;
        overflow: hidden !important;
    }

    /* Selectbox */
    [data-testid="stSelectbox"] > div > div {
        background: #111827 !important;
        border-color: #2d3748 !important;
        border-radius: 10px !important;
        color: #e2e8f0 !important;
    }

    /* Code blocks (forensic summary) */
    .stCodeBlock {
        background: #0d1321 !important;
        border: 1px solid #1e2a3a !important;
        border-radius: 10px !important;
        font-family: 'Inter', monospace !important;
        font-size: 0.87rem !important;
    }

    /* Alert boxes */
    [data-testid="stAlert"] {
        border-radius: 10px !important;
        border-left-width: 4px !important;
    }

    /* Caption */
    .stCaptionContainer, [data-testid="stCaptionContainer"] {
        color: #8892b0 !important;
        font-size: 0.85rem !important;
    }

    /* Info box */
    [data-testid="stInfo"] {
        background: rgba(67,97,238,0.12) !important;
        border-color: #4361ee !important;
        color: #a8b8f8 !important;
        border-radius: 10px !important;
    }

    /* General text */
    p, li, .stMarkdown { color: #c8d6e5 !important; }
    </style>
    """, unsafe_allow_html=True)

    # ── Hero header ────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center; padding: 2.5rem 0 0.25rem;">
        <div style="
            font-family: 'Bebas Neue', 'Space Grotesk', sans-serif;
            font-size: clamp(3rem, 8vw, 5.5rem);
            letter-spacing: 0.18em;
            background: linear-gradient(135deg, #ff6b6b 0%, #e63946 45%, #ff8e53 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1;
            margin-bottom: 0.5rem;
        ">MISS INFORMATION</div>
        <div style="
            height: 3px;
            background: linear-gradient(90deg, transparent, #e63946 30%, #ff8e53 70%, transparent);
            margin: 0.5rem auto 0.9rem;
            max-width: 420px;
            border-radius: 2px;
        "></div>
        <div style="
            font-family: 'Inter', sans-serif;
            font-size: 0.82rem;
            color: #8892b0;
            letter-spacing: 0.28em;
            text-transform: uppercase;
            font-weight: 500;
        ">AI-Powered Misinformation Detection</div>
    </div>
    <div style="height: 1.8rem;"></div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("""
        <div style="
            font-family:'Bebas Neue','Space Grotesk',sans-serif;
            font-size:1.6rem;
            letter-spacing:0.15em;
            background:linear-gradient(135deg,#ff6b6b,#e63946);
            -webkit-background-clip:text;
            -webkit-text-fill-color:transparent;
            background-clip:text;
            margin-bottom:0.2rem;
        ">SETTINGS</div>
        <div style="height:2px;background:linear-gradient(90deg,#e63946,transparent);
            margin-bottom:1.2rem;border-radius:2px;"></div>
        """, unsafe_allow_html=True)
        simulation_mode = st.toggle(
            "Simulation mode",
            value=False,
            help="Skip all API/network calls and return synthetic results (for demos and testing).",
        )

    stage = st.selectbox(
        "Pipeline stage",
        options=[1, 2, 3, 4],
        index=3,
        format_func=lambda s: {
            1: "1 — Scrape post (caption + image URL)",
            2: "2 — + Extract search queries",
            3: "3 — + Fetch context URLs + reverse search + EXIF",
            4: "4 — Full pipeline (embed + anomaly + forensic summary)",
        }[s],
    )

    url_input = st.text_input(
        "Paste a social media post URL",
        placeholder="https://www.instagram.com/p/SHORTCODE/",
    )

    if "analyzing" not in st.session_state:
        st.session_state.analyzing = False

    btn_label = "Analyzing…" if st.session_state.analyzing else "Analyze"
    analyze   = st.button(btn_label, type="primary", disabled=st.session_state.analyzing)

    if analyze and url_input.strip() and not st.session_state.analyzing:
        st.session_state.analyzing = True
        spinner_msg = {
            1: "Scraping post…",
            2: "Scraping + extracting queries…",
            3: "Fetching context URLs + enrichment data…",
            4: "Running full pipeline… this may take 1–2 minutes",
        }[stage]

        try:
            with st.spinner(spinner_msg):
                result = run_pipeline(url_input.strip(), stage=stage, simulation_mode=simulation_mode)
        finally:
            st.session_state.analyzing = False

        # ── Phase 0: Guardrail short-circuit ─────────────────────────────────
        if result.get("guardrail_blocked"):
            st.warning(result["guardrail_reason"])
            if result.get("image_url"):
                _sh("Post image (blocked)")
                try:
                    st.image(load_image_from_url(result["image_url"]), width=400)
                except Exception:
                    st.image(result["image_url"], width=400)
            with st.expander("Raw JSON payload"):
                st.json(result)
            return

        completed_stage = result.get("pipeline_stage", stage)

        # Hard failure: no useful data at all (image download failed, bad URL, etc.)
        if "error" in result and not result.get("gemini_label") and not result.get("forensic_verdict"):
            st.error(f"Pipeline error: {result['error']}")
            st.json(result)
            return

        # Soft failure: stats couldn't run (too few context images) but other results are present
        if result.get("error") and result.get("is_anomaly") is None:
            st.warning(f"Statistical analysis unavailable: {result['error']}")

        if result.get("image_url"):
            _sh("Post image")
            try:
                _display_img = load_image_from_url(result["image_url"])
                st.image(_display_img, width=400)
            except Exception:
                st.image(result["image_url"], width=400)

        if result.get("caption"):
            _sh("Caption")
            st.write(result["caption"])

        if result.get("search_queries"):
            _sh("Search queries")
            for q in result["search_queries"]:
                st.write(f"• {q}")

        if "context_images_fetched" in result:
            st.info(f"Context images fetched: {result['context_images_fetched']}")

        if result.get("context_image_urls_sample"):
            with st.expander("Sample context image URLs (first 20)"):
                for u in result["context_image_urls_sample"]:
                    st.write(u)

        # ── Phase 2.5: Reverse image search + EXIF ───────────────────────────
        rev  = result.get("reverse_image_search", {})
        meta = result.get("image_metadata", {})
        if rev or meta:
            with st.expander("Reverse Image Search & Metadata"):
                if rev:
                    st.markdown("**Reverse Image Search (SerpAPI Google Lens)**")
                    earliest = rev.get("earliest_appearance")
                    if earliest:
                        st.write(f"Earliest appearance : **{earliest.get('date', 'unknown')}**")
                        st.write(f"Source              : {earliest.get('source_name', 'N/A')}")
                        st.write(f"URL                 : {earliest.get('url', 'N/A')}")
                        if earliest.get("title"):
                            st.write(f"Page title          : {earliest['title']}")
                    else:
                        st.write("No dated appearance found.")
                    appearances = rev.get("all_appearances", [])
                    if appearances:
                        domains = list({a.get("source_name") for a in appearances if a.get("source_name")})[:10]
                        st.write(f"Total matches : {len(appearances)}")
                        if domains:
                            st.write("Matched domains : " + ", ".join(domains))
                    st.write(f"Search confidence : {rev.get('search_confidence', 'N/A')}")

                if meta:
                    st.markdown("**Image EXIF Metadata**")
                    st.write(f"Capture timestamp : {meta.get('datetime_original') or 'Stripped / N/A'}")
                    st.write(f"Camera            : {meta.get('camera_make') or 'N/A'} {meta.get('camera_model') or ''}")
                    lat, lon = meta.get("gps_lat"), meta.get("gps_lon")
                    if lat and lon:
                        st.write(f"GPS               : {lat}, {lon}")
                    else:
                        st.write("GPS               : N/A")

        if completed_stage == 4:
            p_value    = result.get("p_value")
            mahal      = result.get("mahalanobis_distance")
            cap_sim    = result.get("caption_image_similarity")

            # Gemini verdict — derive Streamlit level from label emoji
            label  = result.get("gemini_label", "")
            _LEVEL = {"✅": "success", "🔍": "info", "🚨": "error", "⚠️": "error", "❓": "warning"}
            _fn    = next((fn for emoji, fn in _LEVEL.items() if label.startswith(emoji)), "info")
            getattr(st, _fn)(label)

            if result.get("gemini_explanation"):
                st.caption(result["gemini_explanation"])

            col1, col2, col3, col4 = st.columns(4)
            col1.metric(
                "Gemini confidence",
                f"{result.get('gemini_confidence')}%" if result.get("gemini_confidence") is not None else "N/A",
            )
            col2.metric("Mahal. dist.", f"{mahal:.3f}" if mahal is not None else "N/A")
            col3.metric(
                "Caption-image sim.",
                f"{cap_sim:.3f}" if cap_sim is not None else "N/A",
            )
            col4.metric("Context images", result.get("context_images_embedded", 0))

            with st.expander("Detection stats"):
                st.write("Embedding model      : DINOv2 ViT-B/14 (768-D)")
                st.write(f"p-value              : {p_value:.6f}" if p_value is not None else "p-value: N/A")
                st.write(f"PCA components       : {result.get('pca_components_used', 'N/A')}")
                st.write(f"MAD outliers removed : {result.get('outliers_removed_by_mad', 'N/A')}")
                st.write(f"Anomaly threshold (p): {result.get('anomaly_threshold', 0.05)}")

            # ── Phase 5: Forensic Summary ─────────────────────────────────────
            forensic_verdict   = result.get("forensic_verdict", "N/A")
            forensic_reasoning = result.get("forensic_reasoning", "")
            if forensic_verdict or forensic_reasoning:
                _sh("Forensic Summary")
                st.code(
                    f"VERDICT: {forensic_verdict}\n\nREASONING: {forensic_reasoning}",
                    language=None,
                )

            # ── Council breakdown ─────────────────────────────────────────────
            council_scores = result.get("council_scores", {})
            if council_scores:
                _sh("Council Analysis")
                if result.get("council_veto_triggered"):
                    veto_who = (result.get("council_veto_persona") or "unknown").replace("_", " ").title()
                    st.error(f"Hard veto triggered by **{veto_who}**")
                cc1, cc2, cc3 = st.columns(3)
                cc1.metric("Statistical Cynic", f"{council_scores.get('statistical_cynic', 'N/A')}/100")
                cc2.metric("Historian",         f"{council_scores.get('historian',         'N/A')}/100")
                cc3.metric("Linguist",          f"{council_scores.get('linguist',           'N/A')}/100")
                mean = result.get("council_mean_score")
                if mean is not None:
                    st.caption(f"Council mean score: **{mean:.1f} / 100**")

        with st.expander("Raw JSON payload"):
            st.json(result)


if __name__ == "__main__" and not DEV_MODE:
    if len(sys.argv) < 2:
        print("Usage: python MyApp.py <social_media_url>")
        sys.exit(1)
    output = run_pipeline(sys.argv[1])
    print(json.dumps(output, indent=2))

if DEV_MODE:
    _render_ui()