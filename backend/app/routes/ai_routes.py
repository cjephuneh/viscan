from flask.views import MethodView
from flask_smorest import Blueprint

from app.errors import APIError
from app.extensions import db
from app.models import AIResult, Screening, VIAImage
from app.schemas.ai_result import AIResultSchema
from app.schemas.analysis_job import AnalysisJobSchema
from app.schemas.common import DetailSchema
from app.services.queue_service import enqueue_image, present_job

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
    @blp.response(202, AnalysisJobSchema)
    @blp.alt_response(400, schema=DetailSchema)
    @blp.alt_response(404, schema=DetailSchema)
    def post(self, screening_id):
        """Queue the latest image. Returns the job already waiting if one exists."""
        screening = db.session.get(Screening, screening_id)
        if screening is None:
            raise APIError("Screening not found.", 404)

        image = _latest_image(screening)
        job = enqueue_image(image)
        return present_job(job)


@blp.route("/ai-results/<int:result_id>/")
class AIResultDetail(MethodView):
    @blp.response(200, AIResultSchema)
    @blp.alt_response(404, schema=DetailSchema)
    def get(self, result_id):
        result = db.session.get(AIResult, result_id)
        if result is None:
            raise APIError("AI result not found.", 404)
        return result
