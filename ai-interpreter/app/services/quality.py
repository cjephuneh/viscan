import numpy as np
from PIL import Image

MIN_SIDE_PX = 300
ANALYSIS_MAX_SIDE = 1024


def _normalized(img: Image.Image) -> np.ndarray:
    img = img.convert("RGB")
    img.thumbnail((ANALYSIS_MAX_SIDE, ANALYSIS_MAX_SIDE))
    return np.asarray(img, dtype=np.float32)


def assess_quality(img: Image.Image) -> dict:
    """Cheap, local image-quality gate run before spending an API call."""
    width, height = img.size
    rgb = _normalized(img)
    gray = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)

    laplacian = (
        -4 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1] + gray[2:, 1:-1]
        + gray[1:-1, :-2] + gray[1:-1, 2:]
    )
    sharpness = float(laplacian.var())
    brightness = float(gray.mean())
    glare_fraction = float((rgb.min(axis=2) > 245).mean())
    red_dominance = float((rgb[..., 0] > rgb[..., 2] + 15).mean())

    blocking, warnings = [], []
    if min(width, height) < MIN_SIDE_PX:
        blocking.append(f"Resolution too low ({width}x{height}); need at least {MIN_SIDE_PX}px on the short side.")
    if brightness < 40:
        blocking.append("Image is too dark to assess the cervix.")
    if sharpness < 8:
        blocking.append("Image is severely blurred.")
    if brightness > 225:
        warnings.append("Image appears overexposed.")
    if 8 <= sharpness < 25:
        warnings.append("Image is slightly blurred; focus may affect accuracy.")
    if glare_fraction > 0.08:
        warnings.append("Significant specular glare may hide acetowhite areas.")
    if red_dominance < 0.2:
        warnings.append("Image colour profile is atypical for a cervix photo; check framing and lighting.")

    return {
        "acceptable": not blocking,
        "blocking_issues": blocking,
        "warnings": warnings,
        "metrics": {
            "width": width,
            "height": height,
            "brightness": round(brightness, 1),
            "sharpness": round(sharpness, 1),
            "glare_fraction": round(glare_fraction, 4),
            "red_dominance": round(red_dominance, 3),
        },
    }
