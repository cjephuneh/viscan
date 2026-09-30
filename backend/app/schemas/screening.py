from datetime import datetime, timezone

from marshmallow import Schema, fields, validate

from app.models.screening import SCREENING_STATUSES
from app.schemas.assessment import AssessmentSchema
from app.schemas.via_image import VIAImageSchema

PATIENT_CODE = validate.Regexp(
    r"^[A-Za-z0-9][A-Za-z0-9_-]{2,31}$",
    error="patient_code must be 3-32 characters and use letters, numbers, _ or -.",
)
PHONE = validate.Regexp(r"^\+?[0-9]{8,15}$", error="phone must be 8-15 digits, with an optional +.")
NOTIFY_CHANNELS = ("sms", "whatsapp")


def _today():
    return datetime.now(timezone.utc).date()


class ScreeningSchema(Schema):
    id = fields.Integer(dump_only=True)
    facility_id = fields.Integer(required=True)
    patient_code = fields.String(required=True)
    phone = fields.String(allow_none=True)
    notify_channel = fields.String(allow_none=True)
    screening_date = fields.Date(required=True)
    status = fields.String(required=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class ScreeningDetailSchema(ScreeningSchema):
    images = fields.Nested(VIAImageSchema, many=True)
    assessment = fields.Nested(AssessmentSchema, allow_none=True)


class ScreeningCreateSchema(Schema):
    facility_id = fields.Integer(required=True)
    patient_code = fields.String(required=True, validate=PATIENT_CODE)
    phone = fields.String(load_default=None, allow_none=True, validate=PHONE)
    notify_channel = fields.String(
        load_default=None, allow_none=True, validate=validate.OneOf(NOTIFY_CHANNELS)
    )
    screening_date = fields.Date(load_default=_today)


class ScreeningUpdateSchema(Schema):
    patient_code = fields.String(validate=PATIENT_CODE)
    phone = fields.String(allow_none=True, validate=PHONE)
    notify_channel = fields.String(allow_none=True, validate=validate.OneOf(NOTIFY_CHANNELS))
    screening_date = fields.Date()
    status = fields.String(validate=validate.OneOf(SCREENING_STATUSES))


class ScreeningQuerySchema(Schema):
    facility_id = fields.Integer()
    status = fields.String(validate=validate.OneOf(SCREENING_STATUSES))
