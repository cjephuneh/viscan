from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from app.schemas.common import DetailSchema
from app.schemas.integrations import TranslateSchema
from app.services import language_service

blp = Blueprint(
    "language",
    __name__,
    url_prefix="/api/v1/language",
    description="Language translation integration",
)


class TranslateResponseSchema(Schema):
    translated_text = fields.String()
    source_language = fields.String()
    target_language = fields.String()
    provider = fields.String()
    detail = fields.String()


@blp.route("/translate/")
class Translate(MethodView):
    @blp.arguments(TranslateSchema)
    @blp.response(200, TranslateResponseSchema)
    @blp.alt_response(400, schema=DetailSchema)
    @blp.alt_response(502, schema=DetailSchema)
    @blp.alt_response(503, schema=DetailSchema)
    def post(self, data):
        return language_service.translate(
            text=data["text"],
            source_language=data["source_language"],
            target_language=data["target_language"],
        )
