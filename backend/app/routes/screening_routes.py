from flask.views import MethodView
from flask_smorest import Blueprint

from marshmallow import Schema, fields

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
from app.services import patient_notify_service
from app.utils.time import utcnow

blp = Blueprint(
    "screenings",
    __name__,
    url_prefix="/api/v1/screenings",
    description="Screening records",
)


class PatientNotifyResponseSchema(Schema):
    screening_id = fields.Integer()
    channel = fields.String()
    to = fields.String()
    message = fields.String()
    positive = fields.Boolean()
    delivery = fields.Raw()


def _get_screening_or_404(screening_id: int) -> Screening:
    screening = db.session.get(Screening, screening_id)
    if screening is None:
        raise APIError("Screening not found.", 404)
    return screening


def _contact(phone: str | None, notify_channel: str | None) -> tuple[str | None, str | None]:
    phone_value = (phone or "").strip() or None
    channel_value = (notify_channel or "").strip().lower() or None
    if phone_value and not channel_value:
        raise APIError("notify_channel is required when phone is provided.", 400)
    if channel_value and not phone_value:
        raise APIError("phone is required when notify_channel is provided.", 400)
    return phone_value, channel_value


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

        phone, notify_channel = _contact(data.get("phone"), data.get("notify_channel"))
        screening = Screening(
            facility_id=data["facility_id"],
            patient_code=data["patient_code"],
            phone=phone,
            notify_channel=notify_channel,
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
        if "phone" in data or "notify_channel" in data:
            next_phone = data["phone"] if "phone" in data else screening.phone
            next_channel = (
                data["notify_channel"] if "notify_channel" in data else screening.notify_channel
            )
            screening.phone, screening.notify_channel = _contact(next_phone, next_channel)

        screening.updated_at = utcnow()
        db.session.commit()
        return screening


@blp.route("/<int:screening_id>/notify/")
class ScreeningNotify(MethodView):
    @blp.response(200, PatientNotifyResponseSchema)
    @blp.alt_response(400, schema=DetailSchema)
    @blp.alt_response(404, schema=DetailSchema)
    @blp.alt_response(502, schema=DetailSchema)
    @blp.alt_response(503, schema=DetailSchema)
    def post(self, screening_id):
        screening = _get_screening_or_404(screening_id)
        return patient_notify_service.notify_patient(screening)
