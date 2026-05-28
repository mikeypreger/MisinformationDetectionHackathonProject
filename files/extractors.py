import torch
import torchvision.transforms as transforms
from PIL import Image
import requests
from io import BytesIO
import numpy as np

# 1. Load DINOv2 from PyTorch Hub
# 'dinov2_vitb14' is the "Base" size. It is the perfect balance of extreme accuracy and high speed.
print("Loading DINOv2 Model (This will take a few seconds on first run)...")
dinov2 = torch.hub.load('facebookresearch/dinov2', 'dinov2_vitb14')
dinov2.eval() # Set to evaluation mode

# If a GPU is available, move the model there for blazing fast speed
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
dinov2.to(device)

# 2. The DINOv2 Image Preprocessor
# Meta trained DINOv2 on very specific image dimensions and color normalizations
dino_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224), # Must be a multiple of 14 (the patch size)
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

def get_dino_vector(image_source, is_url=False):
    """
    Takes an image, processes it through DINOv2, and returns a geometric feature vector.
    """
    if is_url:
        response = requests.get(image_source)
        img = Image.open(BytesIO(response.content)).convert('RGB')
    else:
        img = Image.open(image_source).convert('RGB')
        
    # Preprocess the image and add a batch dimension [1, 3, 224, 224]
    input_tensor = dino_transform(img).unsqueeze(0).to(device)

    # Pass the image through DINOv2 without tracking gradients (saves memory)
    with torch.no_grad():
        # DINOv2 returns the features. We want the main classification token [CLS]
        features = dinov2(input_tensor)
        
    # Move back to CPU, convert to numpy, and flatten to a 1D array (768 dimensions for vitb14)
    return features.cpu().numpy().flatten()


def get_dino_spatial_vector(image_source, is_url=False):
    """
    Extracts a spatially-aware geometric descriptor using DINOv2 patch tokens.

    Why this beats the CLS token alone:
    A 224x224 image is divided into 16x16 = 256 patches of 14x14 pixels each.
    The CLS token collapses all 256 patches into a single 768-D summary, destroying
    spatial relationships (e.g., which floor a window is on, roofline vs ground level).

    This function builds a 3-level Spatial Pyramid descriptor:
      - CLS token      (768-D): global structural summary
      - Patch mean     (768-D): average content across all 256 patches
      - 2x2 quadrants  (4x768 = 3072-D): NW/NE/SW/SE regional layout

    Total: 4608-D. PCA in the engine will compress this to ~15-40 meaningful dims.
    The quadrant means capture WHERE structural elements (doors, windows, cornices)
    appear in the frame, which the CLS token cannot represent.
    """
    if is_url:
        response = requests.get(image_source)
        img = Image.open(BytesIO(response.content)).convert('RGB')
    else:
        img = Image.open(image_source).convert('RGB')

    input_tensor = dino_transform(img).unsqueeze(0).to(device)

    with torch.no_grad():
        features = dinov2.forward_features(input_tensor)
        cls_token = features['x_norm_clstoken'][0]        # (768,)
        patch_tokens = features['x_norm_patchtokens'][0]  # (256, 768)

    # Reshape flat patch sequence to spatial 16x16 grid
    spatial = patch_tokens.reshape(16, 16, 768)

    # Level 0: global mean over all patches — same information space as CLS but averaged
    patch_mean = spatial.mean(dim=(0, 1))  # (768,)

    # Level 1: 2x2 quadrant means — preserves coarse spatial layout
    # Reshape: (16,16,768) → (2, 8, 2, 8, 768), average over the 8-block dims
    quadrant_means = spatial.reshape(2, 8, 2, 8, 768).mean(dim=(1, 3))  # (2, 2, 768)
    quadrant_means = quadrant_means.reshape(-1)  # (3072,)

    descriptor = torch.cat([cls_token, patch_mean, quadrant_means])
    return descriptor.cpu().numpy()  # (4608,)


if __name__ == "__main__":
    print("Environment check: DINOv2 is ready to go!")