from marshmallow import Schema, fields


class AIResultSchema(Schema):
    id = fields.Integer(dump_only=True)
    via_image_id = fields.Integer(dump_only=True)
    prediction = fields.String()
    confidence = fields.Float()
    model_version = fields.String()
    processing_time_ms = fields.Integer()
    created_at = fields.DateTime(dump_only=True)
