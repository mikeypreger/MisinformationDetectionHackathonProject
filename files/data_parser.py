def parse_instagram(post):
    """Extracts images from Instagram scraped data."""
    images = []
    # 1. Look for a list of photos (carousel or single)
    if "photos" in post and isinstance(post["photos"], list):
        images.extend(post["photos"])
    # 2. Fallback to thumbnail/display url if 'photos' array is missing
    elif "thumbnail" in post and post["thumbnail"]:
        images.append(post["thumbnail"])
    elif "display_url" in post and post["display_url"]:
        images.append(post["display_url"])
    return images

def parse_facebook(post):
    """Extracts images from Facebook scraped data."""
    images = []
    # Facebook Bright Data scrapers usually use these keys
    if "image_url" in post and post["image_url"]:
        images.append(post["image_url"])
    elif "images" in post and isinstance(post["images"], list):
        images.extend(post["images"])
    elif "attachment" in post and isinstance(post["attachment"], dict):
        if "image" in post["attachment"]:
            images.append(post["attachment"]["image"])
    return images

def parse_x(post):
    """Extracts images from X (Twitter) scraped data."""
    images = []
    # X often buries images inside a 'media' or 'extended_entities' array
    if "media" in post and isinstance(post["media"], list):
        for media_item in post["media"]:
            if media_item.get("type") == "photo" and "media_url_https" in media_item:
                images.append(media_item["media_url_https"])
            elif "url" in media_item: # Fallback
                images.append(media_item["url"])
    elif "images" in post and isinstance(post["images"], list):
        images.extend(post["images"])
    return images

def parse_reddit(post):
    """Extracts images from Reddit scraped data."""
    images = []
    # Reddit posts usually have a direct URL if it's an image post
    url = post.get("url", "")
    if url.endswith((".jpg", ".jpeg", ".png")):
        images.append(url)
    # Handle Reddit image galleries
    elif "media_metadata" in post and isinstance(post["media_metadata"], dict):
        for media_id, media_data in post["media_metadata"].items():
            if "s" in media_data and "u" in media_data["s"]:
                # Reddit often escapes URLs in JSON, so we unescape them
                clean_url = media_data["s"]["u"].replace("&amp;", "&")
                images.append(clean_url)
    return images

def parse_tiktok(post):
    """Extracts images from TikTok scraped data (thumbnails or image carousels)."""
    images = []
    # TikTok is mostly video, but we can grab the cover or photo mode images
    if "image_post_info" in post and isinstance(post["image_post_info"], dict):
        if "images" in post["image_post_info"]:
            for img in post["image_post_info"]["images"]:
                if "display_image_url" in img and "url_list" in img["display_image_url"]:
                    images.append(img["display_image_url"]["url_list"][0])
    # Fallback to video thumbnail/cover
    elif "cover" in post and post["cover"]:
        images.append(post["cover"])
    elif "origin_cover" in post and post["origin_cover"]:
        images.append(post["origin_cover"])
    return images

def extract_clean_image_urls(bright_data_json, platform="auto"):
    """
    Main router function. Takes the raw JSON and the platform name.
    Supported platforms: 'instagram', 'facebook', 'x', 'reddit', 'tiktok', or 'auto'.
    """
    clean_urls = []
    
    for post in bright_data_json:
        platform = platform.lower()
        
        if platform == "instagram":
            clean_urls.extend(parse_instagram(post))
        elif platform == "facebook":
            clean_urls.extend(parse_facebook(post))
        elif platform == "x" or platform == "twitter":
            clean_urls.extend(parse_x(post))
        elif platform == "reddit":
            clean_urls.extend(parse_reddit(post))
        elif platform == "tiktok":
            clean_urls.extend(parse_tiktok(post))
        elif platform == "auto":
            # If the friend doesn't know the platform, try them all and grab whatever sticks
            clean_urls.extend(parse_instagram(post))
            clean_urls.extend(parse_facebook(post))
            clean_urls.extend(parse_x(post))
            clean_urls.extend(parse_reddit(post))
            clean_urls.extend(parse_tiktok(post))
            
    # Remove any duplicates or empty strings that might have slipped through
    return list(set(filter(None, clean_urls)))