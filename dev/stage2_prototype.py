import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import torch
import open_clip
import piexif
import json
import requests
import numpy as np
from io import BytesIO
from PIL import Image, UnidentifiedImageError

class Stage2WeakPriors:
    def __init__(self, model_name="ViT-B-32", pretrained="laion2b_s34b_b79k"):
        print("Loading CLIP model for Stage 2...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
        self.model.to(self.device)
        self.tokenizer = open_clip.get_tokenizer(model_name)

    def fetch_image_from_url(self, image_url, use_proxy=False):
        """Fetches image with elite disguise headers and optional proxy tunneling."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
            }
            
            proxies = {}
            if use_proxy:
                # Replace with your friend's Bright Data credentials
                proxy_url = "http://YOUR_BRIGHTDATA_PROXY_CREDENTIALS@brd.superproxy.io:22225"
                proxies = {"http": proxy_url, "https": proxy_url}

            response = requests.get(image_url, headers=headers, proxies=proxies, timeout=15)
            response.raise_for_status() 
            
            # Guardrail 1: Is it actually an image?
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type or not content_type.startswith('image/'):
                print(f"❌ Guardrail Triggered: URL returned webpage/text, not an image ({content_type})")
                return None
                
            return response.content 
        except Exception as e:
            print(f"❌ Network Download Error: {e}") 
            return None

    def extract_exif_date(self, image_bytes):
        try:
            exif_dict = piexif.load(image_bytes)
            if piexif.ExifIFD.DateTimeOriginal in exif_dict["Exif"]:
                return exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal].decode("utf-8")
            return "Stripped"
        except Exception:
            return "Stripped or Invalid EXIF"

    def is_image_corrupted(self, image):
        """Guardrail 2: Check for solid color blocks or zero-variance corruption."""
        # Convert to grayscale and calculate variance of the pixel matrix
        img_array = np.array(image.convert("L")) 
        variance = np.var(img_array)
        
        # A variance < 5.0 indicates a nearly solid block of color
        if variance < 5.0: 
            return True
        return False

    def calculate_clip_friction(self, image, caption_text):
        try:
            image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
            text_tokens = self.tokenizer([caption_text]).to(self.device)

            with torch.no_grad(), torch.cuda.amp.autocast():
                image_features = self.model.encode_image(image_tensor)
                text_features = self.model.encode_text(text_tokens)
                
                image_features /= image_features.norm(dim=-1, keepdim=True)
                text_features /= text_features.norm(dim=-1, keepdim=True)
                
                cosine_similarity = (image_features @ text_features.T).item()
                
            return round(cosine_similarity, 4)
        except Exception as e:
            print(f"❌ CLIP Calculation Error: {e}")
            return None 

    def process_evidence(self, image_url, caption_text, claimed_date=None):
        print(f"[Stage 2] Fetching image from URL...")
        # Note: Flip `use_proxy=True` once you plug in the Bright Data credentials!
        image_bytes = self.fetch_image_from_url(image_url, use_proxy=False) 
        
        if not image_bytes:
            return {
                "stage_status": "FAILED_NETWORK_OR_NOT_IMAGE",
                "error_message": "Could not download a valid image file from the provided URL",
                "metadata": None,
                "clip_friction_score": None
            }

        try:
            # Catch files that claim to be images but have corrupted byte structures
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except UnidentifiedImageError:
            return {
                "stage_status": "FAILED_CORRUPT_BYTES",
                "error_message": "Downloaded file is corrupted and cannot be opened as an image",
                "metadata": None,
                "clip_friction_score": None
            }

        # Apply the mathematical variance check
        if self.is_image_corrupted(image):
            return {
                "stage_status": "FAILED_UNREADABLE_IMAGE",
                "error_message": "Image failed variance check (pitch black, pure white, or corrupted)",
                "metadata": None,
                "clip_friction_score": None
            }

        exif_date = self.extract_exif_date(image_bytes)
        clip_score = self.calculate_clip_friction(image, caption_text)

        if clip_score is None:
            return {
                "stage_status": "FAILED_CLIP_PROCESSING",
                "error_message": "CLIP model failed to process the tensor.",
                "metadata": None,
                "clip_friction_score": None
            }

        return {
            "stage_status": "COMPLETED", 
            "metadata": {
                "exif_original_date": exif_date,
                "claimed_date": claimed_date if claimed_date else "Not provided",
                "c2pa_status": "No C2PA manifest found" 
            },
            "clip_friction_score": clip_score
        }

if __name__ == "__main__":
    print("Initializing system...")
    analyzer = Stage2WeakPriors()
    
    test_url = "https://cdn.britannica.com/37/252437-050-F21BD210/Taylor-Swift-performs-The-Eras-Tour-Sao-Paulo-Brazil-2023.jpg"
    test_caption = "singer." 
    test_date = "2024-05-28"
    
    # 3. Run the analysis
    print("Running analysis...")
    result = analyzer.process_evidence(
        image_url=test_url, 
        caption_text=test_caption, 
        claimed_date=test_date
    )
    
    # 4. Save the results to an actual output document!
    output_filename = "stage2_evidence_output.json"
    with open(output_filename, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=4, ensure_ascii=False)
        
    print(f"✅ Success! Open the '{output_filename}' file in your VS Code folder to see the results.")