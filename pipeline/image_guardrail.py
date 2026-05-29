"""
pipeline/image_guardrail.py  —  Phase 0: Visual Guardrail

Lightweight structural analysis on the query image BEFORE the expensive
context-pool build. Short-circuits the pipeline if the image is unworkable.
"""

import numpy as np
from PIL import Image
from scipy.ndimage import convolve

_LAPLACIAN_KERNEL = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)

_GUARDRAIL_MSG = "N/A — Visual asset contains insufficient data for forensic parsing."

# Thresholds
_BRIGHTNESS_MIN  = 10    # mean pixel value below this → all-black
_BRIGHTNESS_MAX  = 245   # mean pixel value above this → all-white / blown-out
_MONO_STD_MAX    = 8     # std-dev below this → monochrome / near-solid-color
_BLUR_VAR_MIN    = 50    # Laplacian variance below this → severely blurry


def _laplacian_variance(gray_array: np.ndarray) -> float:
    lap = convolve(gray_array.astype(np.float32), _LAPLACIAN_KERNEL)
    return float(lap.var())


def check_image_quality(pil_image: Image.Image) -> tuple[bool, str]:
    """
    Run three structural checks on a PIL image.

    Returns:
        (True, "")              — image passes all checks, pipeline may proceed
        (False, reason_string)  — image is unworkable; caller should short-circuit
    """
    gray = np.array(pil_image.convert("L"), dtype=np.float32)

    mean_val = float(gray.mean())
    if mean_val < _BRIGHTNESS_MIN:
        return False, _GUARDRAIL_MSG

    if mean_val > _BRIGHTNESS_MAX:
        return False, _GUARDRAIL_MSG

    if float(gray.std()) < _MONO_STD_MAX:
        return False, _GUARDRAIL_MSG

    if _laplacian_variance(gray) < _BLUR_VAR_MIN:
        return False, _GUARDRAIL_MSG

<<<<<<< HEAD
    return True, ""
=======
    return True, ""
>>>>>>> db50590cf0fbec53148d22784c379e261240607a
