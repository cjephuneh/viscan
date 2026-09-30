import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

VERDICT_COLOURS = {"SUSPICIOUS": (220, 38, 38), "NOT_SUSPICIOUS": (22, 163, 74), "INDETERMINATE": (107, 114, 128)}
LESION_COLOURS = {"dense": (250, 204, 21), "moderate": (56, 189, 248), "faint": (167, 243, 208)}


def _font(size: int):
    for name in ("Arial.ttf", "DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_overlay(image: bytes | Path, interpretation) -> bytes:
    """Draw approximate lesion boxes, lesion numbers and a verdict banner on the image.

    ``image`` is either the raw image bytes (from blob storage) or a local path.
    """
    source = io.BytesIO(image) if isinstance(image, (bytes, bytearray)) else image
    img = Image.open(source).convert("RGB")
    img.thumbnail((1280, 1280))
    w, h = img.size
    draw = ImageDraw.Draw(img, "RGBA")
    stroke = max(2, w // 300)
    font = _font(max(14, w // 45))

    for number, lesion in enumerate(interpretation.lesions, start=1):
        box = lesion.bbox or {}
        if not box.get("width") or not box.get("height"):
            continue
        x0, y0 = box["x"] * w, box["y"] * h
        x1, y1 = x0 + box["width"] * w, y0 + box["height"] * h
        colour = LESION_COLOURS.get(lesion.density, (250, 204, 21))
        draw.rectangle((x0, y0, x1, y1), outline=colour + (255,), width=stroke)
        draw.rectangle((x0, y0, x1, y1), fill=colour + (40,))
        label = f"{number}: {lesion.clock_start}-{lesion.clock_end} o'clock"
        tw, th = draw.textbbox((0, 0), label, font=font)[2:]
        ty = max(0, y0 - th - 6)
        draw.rectangle((x0, ty, x0 + tw + 8, ty + th + 6), fill=(0, 0, 0, 170))
        draw.text((x0 + 4, ty + 3), label, fill=colour, font=font)

    verdict = interpretation.screening_verdict or "INDETERMINATE"
    banner = f"{verdict.replace('_', ' ')}  |  {interpretation.via_result}  |  risk {interpretation.risk_score if interpretation.risk_score is not None else '-'}"
    th = draw.textbbox((0, 0), banner, font=font)[3]
    draw.rectangle((0, h - th - 14, w, h), fill=VERDICT_COLOURS.get(verdict, (0, 0, 0)) + (210,))
    draw.text((10, h - th - 8), banner, fill=(255, 255, 255), font=font)
    draw.text((w / 2 - 8, 6), "12", fill=(255, 255, 255, 200), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
