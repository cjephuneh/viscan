from marshmallow import Schema, fields

from app.schemas.ai_result import AIResultSchema


class VIAImageSchema(Schema):
    id = fields.Integer(dump_only=True)
    screening_id = fields.Integer(dump_only=True)
    file_path = fields.String(dump_only=True)
    media_type = fields.String(dump_only=True)
    file_size_bytes = fields.Integer(dump_only=True)
    uploaded_at = fields.DateTime(dump_only=True)
    file_url = fields.Method("build_file_url", dump_only=True)
    ai_results = fields.Nested(AIResultSchema, many=True, dump_only=True)

    def build_file_url(self, obj) -> str:
        return f"/api/v1/images/{obj.id}/file"
