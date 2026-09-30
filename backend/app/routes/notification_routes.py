from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from app.schemas.common import DetailSchema
from app.schemas.integrations import SmsSchema
from app.services import sms_service, whatsapp_service

blp = Blueprint(
    "notifications",
    __name__,
    url_prefix="/api/v1/notifications",
    description="SMS and WhatsApp notifications",
)


class NotificationResponseSchema(Schema):
    status = fields.String()
    provider = fields.String()
    to = fields.String()
    message = fields.String()
    detail = fields.String()
    response = fields.Raw()


@blp.route("/sms/")
class SmsNotification(MethodView):
    @blp.arguments(SmsSchema)
    @blp.response(200, NotificationResponseSchema)
    @blp.alt_response(400, schema=DetailSchema)
    @blp.alt_response(502, schema=DetailSchema)
    @blp.alt_response(503, schema=DetailSchema)
    def post(self, data):
        return sms_service.send_sms(to=data["to"], message=data["message"])


@blp.route("/whatsapp/")
class WhatsAppNotification(MethodView):
    @blp.arguments(SmsSchema)
    @blp.response(200, NotificationResponseSchema)
    @blp.alt_response(400, schema=DetailSchema)
    @blp.alt_response(502, schema=DetailSchema)
    @blp.alt_response(503, schema=DetailSchema)
    def post(self, data):
        return whatsapp_service.send_whatsapp(to=data["to"], message=data["message"])
