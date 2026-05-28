import io
import numpy as np
import requests
import torch
from PIL import Image

_model = None
_preprocess = None
_device = None


def load_clip_model():
    """
    Load ViT-B-32 via open_clip (downloads ~350MB on first call).
    Returns (model, preprocess, device). Subsequent calls return cached objects.
    """
    global _model, _preprocess, _device
    if _model is not None:
        return _model, _preprocess, _device

    import open_clip

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[embedder] loading CLIP ViT-B-32 on {_device}...")
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="QuickGELU mismatch")
        _model, _, _preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="openai"
        )
    _model = _model.to(_device).eval()
    print("[embedder] CLIP model ready")
    return _model, _preprocess, _device


def embed_images(pil_images: list, batch_size: int = 32) -> np.ndarray:
    """
    Encode a list of PIL Images with CLIP.
    Returns L2-normalized numpy array of shape (n, 512).
    Images that fail preprocessing are silently skipped.
    """
    model, preprocess, device = load_clip_model()
    all_embeddings = []

    for i in range(0, len(pil_images), batch_size):
        batch = pil_images[i : i + batch_size]
        tensors = []
        for img in batch:
            try:
                tensors.append(preprocess(img))
            except Exception:
                pass
        if not tensors:
            continue
        batch_tensor = torch.stack(tensors).to(device)
        with torch.no_grad():
            feats = model.encode_image(batch_tensor)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        all_embeddings.append(feats.cpu().numpy())

    if not all_embeddings:
        return np.empty((0, 512), dtype=np.float32)

    return np.vstack(all_embeddings).astype(np.float32)


def embed_single_image(pil_image: Image.Image) -> np.ndarray:
    """
    Encode a single PIL Image.
    Returns L2-normalized numpy array of shape (512,).
    """
    result = embed_images([pil_image], batch_size=1)
    if result.shape[0] == 0:
        raise ValueError("Failed to embed the query image")
    return result[0]


def embed_text(text: str) -> np.ndarray:
    """
    Encode a text string with CLIP's text encoder.
    Returns L2-normalized numpy array of shape (512,).

    Cosine similarity between this and an image embedding (dot product of two
    unit vectors) measures how well the image matches the text — the core of
    CLIP's cross-modal alignment.
    """
    import open_clip
    model, _, device = load_clip_model()
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    tokens = tokenizer([text]).to(device)
    with torch.no_grad():
        feat = model.encode_text(tokens)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat[0].cpu().numpy().astype(np.float32)


def load_image_from_url(url: str) -> Image.Image:
    """Download an image URL and return a PIL Image (RGB)."""
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")
