from flask import send_file
from flask.views import MethodView
from flask_smorest import Blueprint
from werkzeug.datastructures import FileStorage

from app.errors import APIError
from app.extensions import db
from app.models import Screening, VIAImage
from app.schemas.common import DetailSchema
from app.schemas.via_image import VIAImageSchema
from app.utils.images import resolve_image_path, validate_and_store_image
from app.utils.time import utcnow

blp = Blueprint(
    "images",
    __name__,
    url_prefix="/api/v1",
    description="VIA image upload and retrieval",
)


def _get_screening_or_404(screening_id: int) -> Screening:
    screening = db.session.get(Screening, screening_id)
    if screening is None:
        raise APIError("Screening not found.", 404)
    return screening


def _get_image_or_404(image_id: int) -> VIAImage:
    image = db.session.get(VIAImage, image_id)
    if image is None:
        raise APIError("Image not found.", 404)
    return image


@blp.route("/screenings/<int:screening_id>/images/")
class ScreeningImageUpload(MethodView):
    @blp.response(201, VIAImageSchema)
    @blp.alt_response(400, schema=DetailSchema)
    @blp.alt_response(404, schema=DetailSchema)
    @blp.alt_response(413, schema=DetailSchema)
    def post(self, screening_id):
        from flask import request

        screening = _get_screening_or_404(screening_id)
        file = request.files.get("file") or request.files.get("image")
        if not isinstance(file, FileStorage):
            raise APIError("Image file is required as multipart field 'file'.", 400)

        relative_path, media_type, size = validate_and_store_image(file, screening.id)
        image = VIAImage(
            screening_id=screening.id,
            file_path=relative_path,
            media_type=media_type,
            file_size_bytes=size,
        )
        screening.status = "IMAGE_UPLOADED"
        screening.updated_at = utcnow()
        db.session.add(image)
        db.session.commit()
        return image


@blp.route("/images/<int:image_id>/")
class ImageDetail(MethodView):
    @blp.response(200, VIAImageSchema)
    @blp.alt_response(404, schema=DetailSchema)
    def get(self, image_id):
        return _get_image_or_404(image_id)


@blp.route("/images/<int:image_id>/file")
class ImageFile(MethodView):
    @blp.alt_response(404, schema=DetailSchema)
    def get(self, image_id):
        image = _get_image_or_404(image_id)
        path = resolve_image_path(image.file_path)
        return send_file(path, mimetype=image.media_type, as_attachment=False)
