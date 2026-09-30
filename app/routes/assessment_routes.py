from flask.views import MethodView
from flask_smorest import Blueprint

from app.errors import APIError
from app.extensions import db
from app.models import Assessment, Screening
from app.schemas.assessment import AssessmentSchema, AssessmentUpdateSchema
from app.schemas.common import DetailSchema
from app.utils.time import utcnow

blp = Blueprint(
    "assessments",
    __name__,
    url_prefix="/api/v1/screenings",
    description="Clinician assessment records",
)


def _get_screening_or_404(screening_id: int) -> Screening:
    screening = db.session.get(Screening, screening_id)
    if screening is None:
        raise APIError("Screening not found.", 404)
    return screening


@blp.route("/<int:screening_id>/assessment/")
class ScreeningAssessment(MethodView):
    @blp.response(200, AssessmentSchema)
    @blp.alt_response(404, schema=DetailSchema)
    def get(self, screening_id):
        screening = _get_screening_or_404(screening_id)
        if screening.assessment is None:
            raise APIError("Assessment not found.", 404)
        return screening.assessment

    @blp.arguments(AssessmentSchema)
    @blp.response(201, AssessmentSchema)
    @blp.alt_response(400, schema=DetailSchema)
    @blp.alt_response(404, schema=DetailSchema)
    @blp.alt_response(409, schema=DetailSchema)
    def post(self, data, screening_id):
        screening = _get_screening_or_404(screening_id)
        if screening.assessment is not None:
            raise APIError("Assessment already exists for this screening.", 409)

        assessment = Assessment(
            screening_id=screening.id,
            result=data["result"],
            notes=data.get("notes"),
        )
        screening.status = "REVIEWED"
        screening.updated_at = utcnow()
        db.session.add(assessment)
        db.session.commit()
        return assessment

    @blp.arguments(AssessmentUpdateSchema)
    @blp.response(200, AssessmentSchema)
    @blp.alt_response(400, schema=DetailSchema)
    @blp.alt_response(404, schema=DetailSchema)
    def patch(self, data, screening_id):
        screening = _get_screening_or_404(screening_id)
        if screening.assessment is None:
            raise APIError("Assessment not found.", 404)
        if not data:
            raise APIError("No fields provided for update.", 400)

        assessment = screening.assessment
        if "result" in data:
            assessment.result = data["result"]
        if "notes" in data:
            assessment.notes = data["notes"]
        assessment.updated_at = utcnow()
        screening.updated_at = utcnow()
        db.session.commit()
        return assessment
