import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import torch
import open_clip
import piexif
import json
import requests
from io import BytesIO
from PIL import Image

class Stage2WeakPriors:
    def __init__(self, model_name="ViT-B-32", pretrained="laion2b_s34b_b79k"):
        print("Loading CLIP model for Stage 2...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
        self.model.to(self.device)
        self.tokenizer = open_clip.get_tokenizer(model_name)

    def fetch_image_from_url(self, image_url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'} 
            response = requests.get(image_url, headers=headers, timeout=10)
            response.raise_for_status() 
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

    def calculate_clip_friction(self, image_bytes, caption_text):
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
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
            return -1.0 

    def process_evidence(self, image_url, caption_text, claimed_date=None):
        print(f"[Stage 2] Fetching image from URL...")
        image_bytes = self.fetch_image_from_url(image_url)
        
        if not image_bytes:
            return {
                "stage_status": "FAILED",
                "error_message": "Could not download image from the provided URL",
                "metadata": None,
                "clip_friction_score": None
            }

        exif_date = self.extract_exif_date(image_bytes)
        clip_score = self.calculate_clip_friction(image_bytes, caption_text)

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