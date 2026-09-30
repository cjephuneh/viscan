from flask.views import MethodView
from flask_smorest import Blueprint

from app.errors import APIError
from app.extensions import db
from app.models import Facility, Screening
from app.schemas.common import DetailSchema
from app.schemas.screening import (
    ScreeningCreateSchema,
    ScreeningDetailSchema,
    ScreeningQuerySchema,
    ScreeningSchema,
    ScreeningUpdateSchema,
)
from app.utils.time import utcnow

blp = Blueprint(
    "screenings",
    __name__,
    url_prefix="/api/v1/screenings",
    description="Screening records",
)


def _get_screening_or_404(screening_id: int) -> Screening:
    screening = db.session.get(Screening, screening_id)
    if screening is None:
        raise APIError("Screening not found.", 404)
    return screening


@blp.route("/")
class ScreeningList(MethodView):
    @blp.arguments(ScreeningQuerySchema, location="query")
    @blp.response(200, ScreeningSchema(many=True))
    def get(self, query_args):
        query = Screening.query.order_by(Screening.id.desc())
        facility_id = query_args.get("facility_id")
        status = query_args.get("status")
        if facility_id is not None:
            query = query.filter_by(facility_id=facility_id)
        if status is not None:
            query = query.filter_by(status=status)
        return query.all()

    @blp.arguments(ScreeningCreateSchema)
    @blp.response(201, ScreeningSchema)
    @blp.alt_response(400, schema=DetailSchema)
    @blp.alt_response(404, schema=DetailSchema)
    @blp.alt_response(409, schema=DetailSchema)
    def post(self, data):
        facility = db.session.get(Facility, data["facility_id"])
        if facility is None or not facility.is_active:
            raise APIError("Facility not found.", 404)

        existing = Screening.query.filter_by(patient_code=data["patient_code"]).first()
        if existing is not None:
            raise APIError("patient_code already exists.", 409)

        screening = Screening(
            facility_id=data["facility_id"],
            patient_code=data["patient_code"],
            screening_date=data["screening_date"],
            status="CREATED",
        )
        db.session.add(screening)
        db.session.commit()
        return screening


@blp.route("/<int:screening_id>/")
class ScreeningDetail(MethodView):
    @blp.response(200, ScreeningDetailSchema)
    @blp.alt_response(404, schema=DetailSchema)
    def get(self, screening_id):
        return _get_screening_or_404(screening_id)

    @blp.arguments(ScreeningUpdateSchema)
    @blp.response(200, ScreeningSchema)
    @blp.alt_response(404, schema=DetailSchema)
    @blp.alt_response(409, schema=DetailSchema)
    def patch(self, data, screening_id):
        screening = _get_screening_or_404(screening_id)
        if not data:
            raise APIError("No fields provided for update.", 400)

        if "patient_code" in data and data["patient_code"] != screening.patient_code:
            conflict = Screening.query.filter_by(patient_code=data["patient_code"]).first()
            if conflict is not None:
                raise APIError("patient_code already exists.", 409)
            screening.patient_code = data["patient_code"]

        if "screening_date" in data:
            screening.screening_date = data["screening_date"]
        if "status" in data:
            screening.status = data["status"]

        screening.updated_at = utcnow()
        db.session.commit()
        return screening
