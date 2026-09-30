from flask import current_app
from flask.views import MethodView
from flask_smorest import Blueprint

from app.errors import APIError
from app.extensions import db
from app.models import AIResult, Screening, VIAImage
from app.schemas.ai_result import AIResultSchema
from app.schemas.common import DetailSchema
from app.services import ai_service
from app.utils.time import utcnow

blp = Blueprint(
    "ai",
    __name__,
    url_prefix="/api/v1",
    description="AI analysis integration",
)


def _latest_image(screening: Screening) -> VIAImage:
    if not screening.images:
        raise APIError("VIA image is required before analysis.", 400)
    return screening.images[-1]


@blp.route("/screenings/<int:screening_id>/analyze/")
class AnalyzeScreening(MethodView):
    @blp.response(201, AIResultSchema)
    @blp.alt_response(400, schema=DetailSchema)
    @blp.alt_response(404, schema=DetailSchema)
    @blp.alt_response(502, schema=DetailSchema)
    @blp.alt_response(503, schema=DetailSchema)
    def post(self, screening_id):
        screening = db.session.get(Screening, screening_id)
        if screening is None:
            raise APIError("Screening not found.", 404)

        image = _latest_image(screening)
        public_base = current_app.config["PUBLIC_BASE_URL"].rstrip("/")
        image_url = f"{public_base}/api/v1/images/{image.id}/file"

        payload = ai_service.analyze_image(image_url=image_url, image_id=image.id)
        result = AIResult(
            via_image_id=image.id,
            prediction=payload["prediction"],
            confidence=payload["confidence"],
            model_version=payload["model_version"],
            processing_time_ms=payload["processing_time_ms"],
        )
        screening.status = "ANALYZED"
        screening.updated_at = utcnow()
        db.session.add(result)
        db.session.commit()
        return result


@blp.route("/ai-results/<int:result_id>/")
class AIResultDetail(MethodView):
    @blp.response(200, AIResultSchema)
    @blp.alt_response(404, schema=DetailSchema)
    def get(self, result_id):
        result = db.session.get(AIResult, result_id)
        if result is None:
            raise APIError("AI result not found.", 404)
        return result
