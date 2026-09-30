import io
import uuid
from pathlib import Path

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.errors import APIError
from app.services.storage import StorageError, get_storage

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

    # Storage key; kept in VIAImage.file_path. Same shape for S3 and local disk.
    storage_key = f"screening_{screening_id}/{uuid.uuid4().hex}{extension}"
    try:
        get_storage().put(storage_key, raw, media_type)
    except StorageError as exc:
        current_app.logger.exception("Image storage failed")
        raise APIError("Image storage is unavailable.", 503) from exc

    return storage_key, media_type, len(raw)


def load_image_bytes(storage_key: str) -> bytes:
    """Read a stored VIA image (S3/MinIO or local disk) by its storage key."""
    if not storage_key or storage_key.startswith("/") or ".." in Path(storage_key).parts:
        raise APIError("Invalid image path.", 400)
    try:
        return get_storage().get(storage_key)
    except FileNotFoundError as exc:
        raise APIError("Image file not found in storage.", 404) from exc
    except StorageError as exc:
        current_app.logger.exception("Image storage read failed")
        raise APIError("Image storage is unavailable.", 503) from exc
