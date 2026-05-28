"""
MyApp.py  —  integrated

Pipeline is locked to DINOv2 ViT-B/14 (768-D) for anomaly detection.
CLIP is still used separately for caption-image similarity scoring.
Gemini multimodal generates the final verdict label.
"""

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

DEV_MODE       = os.getenv("DEV_MODE", "True").lower() == "true"
PIPELINE_STAGE = int(os.getenv("PIPELINE_STAGE", "4"))

from pipeline.url_normalizer    import normalize_url
from pipeline.social_scraper    import scrape_post
from pipeline.caption_extractor import extract_search_queries
from pipeline.image_fetcher     import fetch_context_image_urls, download_images_parallel
from pipeline.embedder          import (
    load_clip_model, embed_images, embed_single_image,
    embed_text, load_image_from_url,
)
from pipeline.anomaly_detector  import run_anomaly_detection
from pipeline.verdict_generator import generate_verdict

if DEV_MODE:
    import streamlit as st

def run_pipeline(
    input_url: str,
    stage: int = PIPELINE_STAGE,
    embedding_model: str = "dino",
    use_gmm: bool = False,
) -> dict:
    """Full pipeline — DINOv2 ViT-B/14 for anomaly detection, CLIP for caption similarity."""

    # Step 1: Normalize URL + scrape post
    try:
        normalized_url, platform_key = normalize_url(input_url)
    except ValueError as e:
        return {"error": str(e), "input_url": input_url}

    post_data  = scrape_post(normalized_url, platform_key)
    image_url  = post_data.get("image_url")
    caption    = post_data.get("caption", "")

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
    context_urls = fetch_context_image_urls(queries, max_total=60)

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

    # Step 4: Full pipeline — download → embed → anomaly + caption score
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

    # Embed with the chosen backend
    context_embeddings = embed_images(context_pil_images, model=embedding_model)
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
        **stats,
    }


# ── Streamlit UI ──────────────────────────────────────────────────────────────


def _render_ui():
    st.set_page_config(page_title="AstroDetect", page_icon="🔭", layout="centered")
    st.title("🔭 AstroDetect")
    st.caption("Cheapfake / out-of-context image detector")

    stage = st.selectbox(
        "Pipeline stage",
        options=[1, 2, 3, 4],
        index=3,
        format_func=lambda s: {
            1: "1 — Scrape post (caption + image URL)",
            2: "2 — + Extract search queries",
            3: "3 — + Fetch context image URLs",
            4: "4 — Full pipeline (embed + anomaly + caption score)",
        }[s],
    )

    if stage == 4:
        with st.spinner("Loading DINOv2 ViT-B/14 model…"):
            from pipeline.embedder import _load_dino_model
            _load_dino_model()

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
            3: "Fetching context image URLs…",
            4: "Running full pipeline… this may take 1–2 minutes",
        }[stage]

        try:
            with st.spinner(spinner_msg):
                result = run_pipeline(
                    url_input.strip(),
                    stage=stage,
                )
        finally:
            st.session_state.analyzing = False

        completed_stage = result.get("pipeline_stage", stage)

        if "error" in result and result.get("is_anomaly") is None and completed_stage < 4:
            st.error(f"Pipeline error: {result['error']}")
            st.json(result)
            return

        if result.get("image_url"):
            st.subheader("Post image")
            st.image(result["image_url"], width=400)

        if result.get("caption"):
            st.subheader("Caption")
            st.write(result["caption"])

        if result.get("search_queries"):
            st.subheader("Search queries")
            for q in result["search_queries"]:
                st.write(f"• {q}")

        if "context_images_fetched" in result:
            st.info(f"Context images fetched: {result['context_images_fetched']}")

        if result.get("context_image_urls_sample"):
            with st.expander("Sample context image URLs (first 20)"):
                for u in result["context_image_urls_sample"]:
                    st.write(u)

        if completed_stage == 4:
            is_anomaly = result.get("is_anomaly")
            p_value    = result.get("p_value")
            mahal      = result.get("mahalanobis_distance")
            cap_sim    = result.get("caption_image_similarity")
            caption    = result.get("caption", "")
            image_url  = result.get("image_url", "")

            with st.spinner("Gemini is reviewing the post…"):
                verdict_fn, verdict_label, verdict_explanation, confidence = generate_verdict(
                    caption=caption,
                    image_url=image_url,
                    is_anomaly=is_anomaly,
                    p_value=p_value,
                    mahalanobis_distance=mahal,
                    caption_image_similarity=cap_sim,
                )
            getattr(st, verdict_fn)(verdict_label)
            if verdict_explanation:
                st.caption(verdict_explanation)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric(
                "Gemini confidence",
                f"{confidence}%" if confidence is not None else "N/A",
                help="How certain Gemini is of its classification (0–100%)",
            )
            col2.metric("Mahal. dist.",
                        f"{mahal:.3f}" if mahal is not None else "N/A")
            col3.metric(
                "Caption-image sim.",
                f"{cap_sim:.3f}" if cap_sim is not None else "N/A",
                help="CLIP cosine similarity between image and caption text",
            )
            col4.metric("Context images", result.get("context_images_embedded", 0))

            with st.expander("Detection stats"):
                st.write(f"Embedding model      : DINOv2 ViT-B/14 (768-D)")
                st.write(f"p-value              : {p_value:.6f}" if p_value is not None else "p-value: N/A")
                st.write(f"PCA components       : {result.get('pca_components_used', 'N/A')}")
                st.write(f"MAD outliers removed : {result.get('outliers_removed_by_mad', 'N/A')}")
                st.write(f"Anomaly threshold (p): {result.get('anomaly_threshold', 0.05)}")
                st.caption(
                    "Anomaly score: visual similarity to context cluster (DINOv2). "
                    "Caption-image score: CLIP cosine similarity between image and caption. "
                    "Final verdict: Gemini multimodal analysis."
                )

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