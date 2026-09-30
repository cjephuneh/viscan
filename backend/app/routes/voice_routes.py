from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from app.schemas.common import DetailSchema
from app.schemas.integrations import SynthesizeSchema
from app.services import voice_service

blp = Blueprint(
    "voice",
    __name__,
    url_prefix="/api/v1/voice",
    description="Voice / avatar integration",
)


class VoiceResponseSchema(Schema):
    status = fields.String()
    provider = fields.String()
    text = fields.String()
    language = fields.String(allow_none=True)
    detail = fields.String()
    response = fields.Raw()


@blp.route("/synthesize/")
class Synthesize(MethodView):
    @blp.arguments(SynthesizeSchema)
    @blp.response(200, VoiceResponseSchema)
    @blp.alt_response(400, schema=DetailSchema)
    @blp.alt_response(502, schema=DetailSchema)
    @blp.alt_response(503, schema=DetailSchema)
    def post(self, data):
        return voice_service.synthesize(
            text=data["text"],
            language=data.get("language"),
        )
