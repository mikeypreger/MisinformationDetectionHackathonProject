import json
import os
import sys
from pipeline.url_normalizer import normalize_url
from pipeline.social_scraper import scrape_post
from pipeline.caption_extractor import extract_search_queries
from pipeline.image_fetcher import fetch_context_image_urls, download_images_parallel
from pipeline.embedder import load_clip_model, embed_images, embed_single_image, load_image_from_url
from pipeline.anomaly_detector import run_anomaly_detection

from dotenv import load_dotenv
from streamlit import caption

load_dotenv()

# ── Mode flags ────────────────────────────────────────────────────────────────
# DEV_MODE:      True  → Streamlit UI | False → JSON stdout (set via env or flip here)
# PIPELINE_STAGE: 1-4 → how deep the pipeline runs (set via env or UI selectbox)
#   1 = URL normalize + scrape (caption + image URL)
#   2 = + extract search queries
#   3 = + fetch context image URLs (no download/embed)
#   4 = full pipeline (download → CLIP → anomaly stats)  [default]
DEV_MODE = os.getenv("DEV_MODE", "True").lower() == "true"
PIPELINE_STAGE = int(os.getenv("PIPELINE_STAGE", "3"))
# ─────────────────────────────────────────────────────────────────────────────

from pipeline.url_normalizer import normalize_url
from pipeline.social_scraper import scrape_post
from pipeline.caption_extractor import extract_search_queries
from pipeline.image_fetcher import fetch_context_image_urls, download_images_parallel
from pipeline.embedder import load_clip_model, embed_images, embed_single_image, load_image_from_url
from pipeline.anomaly_detector import run_anomaly_detection

if DEV_MODE:
    import streamlit as st


def run_pipeline(input_url: str, stage: int = PIPELINE_STAGE) -> dict:
    """
    Full pipeline: URL → anomaly verdict JSON.
    stage controls how many steps to run (1–4); useful for incremental debugging.
    """

    # Step 1: Normalize URL + scrape post
    try:
        normalized_url, platform_key = normalize_url(input_url)
    except ValueError as e:
        return {"error": str(e), "input_url": input_url}

    post_data = scrape_post(normalized_url, platform_key)
    image_url = post_data.get("image_url")
    caption = post_data.get("caption", "")

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

    # Step 2: Extract search queries from caption
    queries = extract_search_queries(caption, post_url=normalized_url)

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

    # Step 3: Fetch context image URLs (no download yet)
    context_urls = fetch_context_image_urls(queries, max_total=500)

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
            "pipeline_stage": 3,
        }

    # Step 4: Full pipeline — download → CLIP → anomaly detection
    context_pil_images = download_images_parallel(context_urls)

    try:
        query_pil = load_image_from_url(image_url)
    except Exception as e:
        return {
            "error": f"Failed to download post image: {e}",
            "image_url": image_url,
            "caption": caption,
            "search_queries": queries,
            "pipeline_stage": 4,
        }

    import numpy as np

    context_embeddings = embed_images(context_pil_images)
    query_embedding = embed_single_image(query_pil)
    stats = run_anomaly_detection(context_embeddings, query_embedding)

    return {
        "input_url": input_url,
        "normalized_url": normalized_url,
        "platform": platform_key,
        "image_url": image_url,
        "caption": caption,
        "search_queries": queries,
        "context_images_fetched": len(context_urls),
        "context_images_embedded": int(context_embeddings.shape[0]),
        "pipeline_stage": 4,
        **stats,
    }


# ── Streamlit UI (DEV_MODE=True) ─────────────────────────────────────────────

def _render_ui():
    st.set_page_config(page_title="AstroDetect", page_icon="🔭", layout="centered")
    st.title("🔭 AstroDetect")
    st.caption("Cheapfake / out-of-context image detector — Hackathon 2026")

    stage = st.selectbox(
        "Pipeline stage",
        options=[1, 2, 3, 4],
        index=3,
        format_func=lambda s: {
            1: "1 — Scrape post (caption + image URL)",
            2: "2 — + Extract search queries",
            3: "3 — + Fetch context image URLs",
            4: "4 — Full pipeline (CLIP + anomaly score)",
        }[s],
    )

    if stage == 4:
        with st.spinner("Loading CLIP model…"):
            load_clip_model()

    url_input = st.text_input(
        "Paste a social media post URL",
        placeholder="https://www.instagram.com/p/SHORTCODE/",
    )

    if "analyzing" not in st.session_state:
        st.session_state.analyzing = False

    btn_label = "Analyzing…" if st.session_state.analyzing else "Analyze"
    analyze = st.button(
        btn_label, type="primary",
        disabled=st.session_state.analyzing,
    )

    if analyze and url_input.strip() and not st.session_state.analyzing:
        st.session_state.analyzing = True
        spinner_msg = {
            1: "Scraping post…",
            2: "Scraping + extracting queries…",
            3: "Fetching context image URLs…",
            4: "Running full pipeline… this may take 1-2 minutes",
        }[stage]

        try:
            with st.spinner(spinner_msg):
                result = run_pipeline(url_input.strip(), stage=stage)
        finally:
            st.session_state.analyzing = False

        # Always show raw JSON for partial stages
        completed_stage = result.get("pipeline_stage", stage)

        if "error" in result and result.get("is_anomaly") is None and completed_stage < 4:
            st.error(f"Pipeline error: {result['error']}")
            st.json(result)
            return

        # Stage 1+ output
        if result.get("image_url"):
            st.subheader("Post image")
            st.image(result["image_url"], use_container_width=False, width=400)

        if result.get("caption"):
            st.subheader("Caption")
            st.write(result["caption"])

        # Stage 2+ output
        if result.get("search_queries"):
            st.subheader("Search queries")
            for q in result["search_queries"]:
                st.write(f"• {q}")

        # Stage 3+ output
        if "context_images_fetched" in result:
            st.info(f"Context images fetched: {result['context_images_fetched']}")

        if result.get("context_image_urls_sample"):
            with st.expander("Sample context image URLs (first 20)"):
                for u in result["context_image_urls_sample"]:
                    st.write(u)

        # Stage 4 verdict
        if completed_stage == 4:
            is_anomaly = result.get("is_anomaly")
            p_value = result.get("p_value")
            mahal = result.get("mahalanobis_distance")

            if is_anomaly is True:
                st.error("⚠️ ANOMALY DETECTED — image is likely out of context")
            elif is_anomaly is False:
                st.success("✅ Image appears consistent with context")
            else:
                st.warning("⚠️ Inconclusive — not enough data")

            col1, col2, col3 = st.columns(3)
            col1.metric("p-value", f"{p_value:.4f}" if p_value is not None else "N/A")
            col2.metric("Mahalanobis dist.", f"{mahal:.3f}" if mahal is not None else "N/A")
            col3.metric("Context images embedded", result.get("context_images_embedded", 0))

            with st.expander("Detection stats"):
                st.write(f"PCA components: {result.get('pca_components_used', 'N/A')}")
                st.write(f"MAD outliers removed: {result.get('outliers_removed_by_mad', 'N/A')}")
                st.write(f"Anomaly threshold (p): {result.get('anomaly_threshold', 0.05)}")

        with st.expander("Raw JSON payload"):
            st.json(result)


# ── CLI entry point (DEV_MODE=False) ─────────────────────────────────────────

if __name__ == "__main__" and not DEV_MODE:
    if len(sys.argv) < 2:
        print("Usage: python MyApp.py <social_media_url>")
        sys.exit(1)
    output = run_pipeline(sys.argv[1])
    print(json.dumps(output, indent=2))


# Streamlit executes module-level code on import; render UI here
if DEV_MODE:
    _render_ui()
