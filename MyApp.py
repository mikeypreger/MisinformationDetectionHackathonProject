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
from pipeline.social_scraper    import scrape_post
from pipeline.caption_extractor import extract_search_queries
from pipeline.image_fetcher     import fetch_context_image_urls, download_images_parallel
from pipeline.embedder          import (
    load_clip_model, embed_images, embed_single_image,
    embed_text, load_image_from_url,
)
from pipeline.anomaly_detector  import run_anomaly_detection
from pipeline.verdict_generator import generate_verdict
from pipeline.image_guardrail   import check_image_quality
from pipeline.context_enricher  import run_reverse_image_search, extract_image_metadata
from pipeline.forensic_summarizer import generate_forensic_summary

if DEV_MODE:
    import streamlit as st

def run_pipeline(
    input_url: str,
    stage: int = PIPELINE_STAGE,
    embedding_model: str = "dino",
    use_gmm: bool = False,
) -> dict:
    """Full pipeline — DINOv2 ViT-B/14 for anomaly detection, CLIP for caption similarity."""

    # ── Stage 1: Normalize URL + scrape post ─────────────────────────────────
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

    # ── Stage 2: Extract search queries from caption ──────────────────────────
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

    # ── Phase 2.5: Context Enrichment (runs in parallel with context-pool fetch) ──
    # Reverse image search and EXIF extraction happen while we build the context pool.
    reverse_search  = run_reverse_image_search(image_url)
    image_metadata  = extract_image_metadata(image_url)

    # ── Stage 3: Fetch context image URLs ────────────────────────────────────
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
            "reverse_image_search": reverse_search,
            "image_metadata": image_metadata,
            "pipeline_stage": 3,
        }

    # ── Stage 4: Full pipeline — embed → anomaly + caption score ─────────────
    context_pil_images = download_images_parallel(context_urls)

    import numpy as np

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

    # Gemini multimodal verdict (existing flow — unchanged)
    _, verdict_label, verdict_explanation, confidence = generate_verdict(
        caption=caption,
        image_url=image_url,
        is_anomaly=stats.get("is_anomaly"),
        p_value=stats.get("p_value"),
        mahalanobis_distance=stats.get("mahalanobis_distance"),
        caption_image_similarity=caption_image_similarity,
        reverse_search=reverse_search,
    )

    # ── Phase 5: Forensic Summary ─────────────────────────────────────────────
    forensic_stats = {
        **stats,
        "context_images_embedded": int(context_embeddings.shape[0]),
    }
    forensic = generate_forensic_summary(
        caption=caption,
        image_metadata=image_metadata,
        stats=forensic_stats,
        reverse_search=reverse_search,
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
        # Phase 2.5
        "reverse_image_search": reverse_search,
        "image_metadata": image_metadata,
        # Existing Gemini verdict
        "gemini_label": verdict_label,
        "gemini_confidence": confidence,
        "gemini_explanation": verdict_explanation,
        # Phase 5
        "forensic_verdict": forensic.get("verdict", "N/A"),
        "forensic_reasoning": forensic.get("reasoning", ""),
        **stats,
    }


# ── Streamlit UI ──────────────────────────────────────────────────────────────


def _render_ui():
    st.set_page_config(page_title="Miss Information", page_icon="🔍", layout="centered")
    st.title("🔍 Miss Information")
    st.caption("Misinformation detection powered by statistical forensics")

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
                result = run_pipeline(url_input.strip(), stage=stage)
        finally:
            st.session_state.analyzing = False

        # ── Phase 0: Guardrail short-circuit ─────────────────────────────────
        if result.get("guardrail_blocked"):
            st.warning(result["guardrail_reason"])
            if result.get("image_url"):
                st.subheader("Post image (blocked)")
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
            st.subheader("Post image")
            try:
                _display_img = load_image_from_url(result["image_url"])
                st.image(_display_img, width=400)
            except Exception:
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
                st.subheader("Forensic Summary")
                st.code(
                    f"VERDICT: {forensic_verdict}\n\nREASONING: {forensic_reasoning}",
                    language=None,
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
