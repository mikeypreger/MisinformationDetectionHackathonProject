"""
embedder.py  —  integrated

Adds DINOv2 spatial-pyramid embeddings (768-D / 4608-D) alongside the original
CLIP embeddings (512-D).  Callers choose a backend via the `model` parameter.

Backends
--------
"clip"  (default, unchanged)
    ViT-B/32 via open_clip. L2-normalised 512-D vectors.
    Fast, good for cross-modal caption↔image similarity.

"dino"
    DINOv2 ViT-B/14 CLS token. 768-D geometric descriptor.
    Captures structural / architectural features better than CLIP.

"dino_spatial"
    DINOv2 CLS + patch mean + 2×2 quadrant means. 4608-D.
    Preserves spatial layout (where doors/windows appear in frame).
    Slower but best for detecting recontextualised photos.

Public API
----------
embed_images(pil_images, batch_size, model)  →  (n, D) float32
embed_single_image(pil_image, model)         →  (D,)   float32
embed_text(text)                             →  (512,) float32  [CLIP only]
load_image_from_url(url)                     →  PIL.Image
load_clip_model()                            →  (model, preprocess, device)
"""

import io
import warnings
import numpy as np
import requests
import torch
from PIL import Image

# ── Lazy singletons ──────────────────────────────────────────────────────────
_clip_model      = None
_clip_preprocess = None
_clip_device     = None

_dino_model      = None
_dino_transform  = None
_dino_device     = None


# ── CLIP ─────────────────────────────────────────────────────────────────────

def load_clip_model():
    """Load ViT-B/32 via open_clip (downloads ~350 MB on first call)."""
    global _clip_model, _clip_preprocess, _clip_device
    if _clip_model is not None:
        return _clip_model, _clip_preprocess, _clip_device

    import open_clip

    _clip_device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[embedder] loading CLIP ViT-B/32 on {_clip_device}…")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="QuickGELU mismatch")
        _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="openai"
        )
    _clip_model = _clip_model.to(_clip_device).eval()
    print("[embedder] CLIP ready")
    return _clip_model, _clip_preprocess, _clip_device


# ── DINOv2 ───────────────────────────────────────────────────────────────────

def _patch_dino_no_xformers(model) -> None:
    """
    DINOv2 detects xFormers at import time and routes attention through
    memory_efficient_attention_forward, which only supports CUDA + float16/bfloat16.
    On CPU + float32 every forward pass crashes.

    Fix: rebind each MemEffAttention instance's forward to its parent
    Attention.forward, which uses standard PyTorch scaled-dot-product attention.
    """
    for module in model.modules():
        cls = type(module)
        if cls.__name__ == "MemEffAttention":
            parent_forward = cls.__bases__[0].forward
            module.forward = parent_forward.__get__(module, cls)


def _load_dino_model():
    """Load DINOv2 ViT-B/14 from PyTorch Hub (downloads ~330 MB on first call)."""
    global _dino_model, _dino_transform, _dino_device
    if _dino_model is not None:
        return _dino_model, _dino_transform, _dino_device

    import torchvision.transforms as T

    _dino_device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[embedder] loading DINOv2 ViT-B/14 on {_dino_device}…")
    _dino_model = torch.hub.load("facebookresearch/dinov2", "dinov2_vitb14")
    _patch_dino_no_xformers(_dino_model)   # force standard attention on CPU
    _dino_model = _dino_model.to(_dino_device).eval()

    # Exact normalisation Meta used during DINOv2 pre-training
    _dino_transform = T.Compose([
        T.Resize(256),
        T.CenterCrop(224),   # must be a multiple of patch size 14
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    print("[embedder] DINOv2 ready")
    return _dino_model, _dino_transform, _dino_device


# ── Per-image feature extraction ─────────────────────────────────────────────

def _dino_cls_vector(pil_image: Image.Image) -> np.ndarray:
    """DINOv2 CLS token → (768,) float32."""
    model, transform, device = _load_dino_model()
    tensor = transform(pil_image).unsqueeze(0).to(device)
    with torch.no_grad():
        vec = model(tensor)
    return vec.cpu().numpy().flatten().astype(np.float32)


def _dino_spatial_vector(pil_image: Image.Image) -> np.ndarray:
    """
    DINOv2 3-level spatial pyramid → (4608,) float32.

    Levels:
      CLS token  (768-D)  — global structural summary
      Patch mean (768-D)  — average across all 256 patches
      2×2 quads  (3072-D) — NW/NE/SW/SE regional layout

    The quadrant means capture WHERE structural elements appear in the frame,
    which the CLS token alone cannot represent.
    """
    model, transform, device = _load_dino_model()
    tensor = transform(pil_image).unsqueeze(0).to(device)

    with torch.no_grad():
        feats = model.forward_features(tensor)
        cls_token    = feats["x_norm_clstoken"][0]       # (768,)
        patch_tokens = feats["x_norm_patchtokens"][0]    # (256, 768)

    # Reshape flat 256-token sequence → spatial 16×16 grid
    spatial = patch_tokens.reshape(16, 16, 768)

    patch_mean     = spatial.mean(dim=(0, 1))            # (768,)
    quadrant_means = (
        spatial.reshape(2, 8, 2, 8, 768)
               .mean(dim=(1, 3))
               .reshape(-1)                              # (3072,)
    )

    descriptor = torch.cat([cls_token, patch_mean, quadrant_means])
    return descriptor.cpu().numpy().astype(np.float32)   # (4608,)


# ── Public batch API ─────────────────────────────────────────────────────────

def embed_images(
    pil_images: list,
    batch_size: int = 32,
    model: str = "clip",
) -> np.ndarray:
    """
    Encode a list of PIL Images.

    Parameters
    ----------
    pil_images : list of PIL.Image
    batch_size : int   (only used for CLIP; DINOv2 runs one image at a time)
    model      : "clip" | "dino" | "dino_spatial"

    Returns
    -------
    np.ndarray  shape (n, D), float32, L2-normalised for CLIP
    """
    if not pil_images:
        D = {"clip": 512, "dino": 768, "dino_spatial": 4608}.get(model, 512)
        return np.empty((0, D), dtype=np.float32)

    # ── DINOv2 paths ─────────────────────────────────────────────────────────
    if model in ("dino", "dino_spatial"):
        extractor = _dino_cls_vector if model == "dino" else _dino_spatial_vector
        vecs = []
        for img in pil_images:
            try:
                vecs.append(extractor(img))
            except Exception as e:
                print(f"[embedder] DINOv2 skipping image: {e}")
        return np.vstack(vecs).astype(np.float32) if vecs else np.empty((0, 768 if model == "dino" else 4608), dtype=np.float32)

    # ── CLIP path (original, unchanged) ─────────────────────────────────────
    clip_model, preprocess, device = load_clip_model()
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
            feats = clip_model.encode_image(batch_tensor)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        all_embeddings.append(feats.cpu().numpy())

    if not all_embeddings:
        return np.empty((0, 512), dtype=np.float32)
    return np.vstack(all_embeddings).astype(np.float32)


def embed_single_image(
    pil_image: Image.Image,
    model: str = "clip",
) -> np.ndarray:
    """
    Encode a single PIL Image.
    Returns float32 array of shape (D,).
    """
    result = embed_images([pil_image], batch_size=1, model=model)
    if result.shape[0] == 0:
        raise ValueError("Failed to embed the query image")
    return result[0]


def embed_text(text: str) -> np.ndarray:
    """
    Encode a text string with CLIP's text encoder → (512,) float32.
    (CLIP only — DINOv2 is vision-only.)
    """
    import open_clip
    clip_model, _, device = load_clip_model()
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    tokens = tokenizer([text]).to(device)
    with torch.no_grad():
        feat = clip_model.encode_text(tokens)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat[0].cpu().numpy().astype(np.float32)


def load_image_from_url(url: str) -> Image.Image:
    """Download an image URL and return a PIL Image (RGB)."""
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")