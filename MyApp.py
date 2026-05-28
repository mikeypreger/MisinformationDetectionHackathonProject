import os
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv
import streamlit as st

# =====================================================================
# 1. INITIALIZATION & SECURITY LAYER
# =====================================================================
# Load the hidden configurations from your local .env file
load_dotenv()

BD_TOKEN = os.getenv("BRIGHT_DATA_TOKEN")
SCRAPER_MAP = {
    "reddit.com": os.getenv("ID_REDDIT"),
    "instagram.com": os.getenv("ID_INSTAGRAM"),
    "twitter.com": os.getenv("ID_TWITTER"),
    "x.com": os.getenv("ID_TWITTER"),
    "tiktok.com": os.getenv("ID_TIKTOK"),
    "facebook.com": os.getenv("ID_FACEBOOK")
}
GOOGLE_IMAGES_ID = os.getenv("ID_GOOGLE_IMAGES")

# Fail-fast check to protect your hackathon presentation flow
if not BD_TOKEN or "PASTE_YOUR" in str(GOOGLE_IMAGES_ID):
    st.error("⚠️ Environment Configuration Error: Please check your .env file keys.")

# =====================================================================
# 2. PHASE 1: TARGET SOCIAL MEDIA INGESTION
# =====================================================================
def extract_target_post(social_url: str) -> tuple:
    """
    Inspects the input link, automatically routes it to the matching 
    Bright Data platform scraper, and pulls the target image and caption text.
    """
    domain = urlparse(social_url).netloc.lower()
    # Remove 'www.' prefix if present to normalize matching
    domain_clean = domain.replace("www.", "")
    
    dataset_id = None
    for key, val in SCRAPER_MAP.items():
        if key in domain_clean:
            dataset_id = val
            break
            
    if not dataset_id:
        raise ValueError(f"Domain '{domain_clean}' is not supported by our ingestion routing map.")

    endpoint = f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&notify=false&include_errors=true"
    headers = {"Authorization": f"Bearer {BD_TOKEN}", "Content-Type": "application/json"}
    
    # Platform target scrapers expect the structured URL input wrapper
    payload = {"input": [{"url": social_url}]}
    
    response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"Bright Data platform fetch failed: {response.status_code}")
        
    records = response.json()
    if not records:
        return None, None
        
    post_data = records[0]
    
    # Polymorphic parser: Defensively extract caption and media across platform variations
    caption = post_data.get("caption") or post_data.get("text") or post_data.get("content") or post_data.get("title", "")
    image_url = post_data.get("display_url") or post_data.get("image_url") or post_data.get("media_url")
    
    # Special nested handling for complex platforms like Reddit galleries
    if not image_url and "media_gallery" in post_data and post_data["media_gallery"]:
        image_url = post_data["media_gallery"][0].get("url") or post_data["media_gallery"][0].get("image_url")

    return image_url, caption

# =====================================================================
# 3. PHASE 2: CROSS-WEB MULTI-SOURCE CONTEXT DISCOVERY
# =====================================================================
def harvest_google_images(caption_query: str, max_records: int = 100) -> list:
    """
    Executes a real-time synchronous query to the Google SERP scraper,
    forcing image search mode via 'tbm':'isch' to build our context pool.
    """
    endpoint = f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={GOOGLE_IMAGES_ID}&notify=false&include_errors=true"
    headers = {"Authorization": f"Bearer {BD_TOKEN}", "Content-Type": "application/json"}
    
    # Exact structure copied from your dashboard layout, integrating our safety limit
    payload = {
        "input": [
            {
                "url": "https://www.google.com/",
                "keyword": caption_query,
                "tbm": "isch",
                "limit": max_records,
                "language": "en"
            }
        ]
    }
    
    response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"Bright Data search fetch failed: {response.status_code}")
        
    records = response.json()
    image_urls = []
    
    for record in records:
        if "images_results" in record:
            for img_node in record["images_results"]:
                if "original" in img_node:
                    image_urls.append(img_node["original"])
        elif "organic" in record:
            for item in record.get("organic", []):
                if "image" in item:
                    image_urls.append(item["image"])
                    
    return list(set(image_urls))

# =====================================================================
# 4. STREAMLIT BACKEND RUNTIME INTERFACE
# =====================================================================
st.set_page_config(page_title="AstroDetect Terminal", layout="wide")
st.markdown("# 🌌 AstroDetect: AI Integrity Verification Layer")
st.markdown("---")

input_url = st.text_input("🔗 Paste Social Media Link Target (X, Reddit, Instagram, Facebook, TikTok):")

if st.button("🚀 Analyze Post & Extract Context Pool", use_container_width=True):
    if not input_url:
        st.warning("Please provide a valid URL link target first.")
    else:
        try:
            with st.spinner("Executing Phase 1: Contacting platform scraper..."):
                target_img, extracted_caption = extract_target_post(input_url)
                
            if not extracted_caption:
                st.error("Could not parse a caption context from this post layout. Is the link private or invalid?")
            else:
                st.success("🎯 Phase 1 Complete! Target asset isolated.")
                
                # Show extracted data layout to user
                col1, col2 = st.columns([1, 2])
                with col1:
                    if target_img:
                        st.image(target_img, caption="Query Target Image Extracted From Link", use_container_width=True)
                with col2:
                    st.info(f"**Extracted Caption Text:**\n\n{extracted_caption}")
                
                # Automatically trigger Phase 2 using the newly captured text
                with st.spinner("Executing Phase 2: Generating cross-web image manifold via Google..."):
                    context_pool = harvest_google_images(extracted_caption, max_records=100)
                    
                st.success(f"📈 Phase 2 Complete! Built a context manifold containing {len(context_pool)} unique web assets.")
                
                # Preview top links retrieved
                with st.expander("🔍 Inspect Sample Harvested Manifold URLs"):
                    for url in context_pool[:5]:
                        st.write(f"🔗 {url}")
                        
        except Exception as e:
            st.error(f"Execution Failure: {str(e)}")