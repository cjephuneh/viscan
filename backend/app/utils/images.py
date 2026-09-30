import io
import uuid
from pathlib import Path

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.errors import APIError

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def _extension_for(fmt: str) -> str:
    if fmt == "JPEG":
        return ".jpg"
    if fmt == "PNG":
        return ".png"
    if fmt == "WEBP":
        return ".webp"
    raise APIError("Unsupported image format.", 400)


def validate_and_store_image(file: FileStorage, screening_id: int) -> tuple[str, str, int]:
    if file is None or not getattr(file, "filename", None):
        raise APIError("Image file is required.", 400)

    original = secure_filename(file.filename)
    if not original:
        raise APIError("Invalid image filename.", 400)

    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise APIError("Unsupported image format. Use JPEG, PNG, or WEBP.", 400)

    raw = file.read()
    if not raw:
        raise APIError("Uploaded image is empty.", 400)

    max_bytes = current_app.config["MAX_UPLOAD_BYTES"]
    if len(raw) > max_bytes:
        raise APIError("Image exceeds the maximum file size.", 413)

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            fmt = (image.format or "").upper()
            if fmt not in ALLOWED_FORMATS:
                raise APIError("Unsupported image format. Use JPEG, PNG, or WEBP.", 400)
            media_type = ALLOWED_FORMATS[fmt]
            extension = _extension_for(fmt)
    except UnidentifiedImageError as exc:
        raise APIError("File content is not a valid image.", 400) from exc
    except OSError as exc:
        raise APIError("File content is not a valid image.", 400) from exc

    upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    screening_dir = upload_root / f"screening_{screening_id}"
    screening_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{extension}"
    absolute_path = screening_dir / filename
    absolute_path.write_bytes(raw)

    relative_path = absolute_path.relative_to(upload_root).as_posix()
    return relative_path, media_type, len(raw)


def resolve_image_path(relative_path: str) -> Path:
    upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    candidate = (upload_root / relative_path).resolve()
    if upload_root not in candidate.parents and candidate != upload_root:
        raise APIError("Invalid image path.", 400)
    if not candidate.is_file():
        raise APIError("Image file not found on disk.", 404)
    return candidate
