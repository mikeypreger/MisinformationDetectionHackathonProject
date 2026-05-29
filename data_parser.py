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
    # 1. Direct post image field (Bright Data Facebook schema)
    if "post_image" in post and post["post_image"]:
        images.append(post["post_image"])
    # 2. Attachments array — grab photo-type attachment URLs
    if not images and "attachments" in post and isinstance(post["attachments"], list):
        for attachment in post["attachments"]:
            if isinstance(attachment, dict) and attachment.get("type") == "photo":
                url = attachment.get("url")
                if url:
                    images.append(url)
    # 3. Legacy / alternative field names
    if not images:
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
    # 1. Direct image link (i.redd.it or external image URL)
    url = post.get("url", "")
    if url and any(url.lower().split("?")[0].endswith(ext)
                   for ext in (".jpg", ".jpeg", ".png", ".webp")):
        images.append(url)
    # 2. Preview image — most common for link posts and crossposts
    if not images:
        preview = post.get("preview") or {}
        imgs = preview.get("images", [])
        if imgs and isinstance(imgs, list):
            source = imgs[0].get("source", {})
            src_url = source.get("url", "")
            if src_url:
                images.append(src_url.replace("&amp;", "&"))
    # 3. Gallery posts (media_metadata)
    if not images and "media_metadata" in post and isinstance(post["media_metadata"], dict):
        for media_data in post["media_metadata"].values():
            if isinstance(media_data, dict) and "s" in media_data:
                u = media_data["s"].get("u", "")
                if u:
                    images.append(u.replace("&amp;", "&"))
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