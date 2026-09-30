from marshmallow import Schema, fields

from app.schemas.ai_result import AIResultSchema


class AnalysisJobSchema(Schema):
    id = fields.Integer(dump_only=True)
    via_image_id = fields.Integer(dump_only=True)
    screening_id = fields.Integer(dump_only=True)
    status = fields.String(dump_only=True)
    position = fields.Integer(allow_none=True, dump_only=True)
    ahead = fields.Integer(allow_none=True, dump_only=True)
    attempts = fields.Integer(dump_only=True)
    error_detail = fields.String(allow_none=True, dump_only=True)
    ai_result_id = fields.Integer(allow_none=True, dump_only=True)
    queued_at = fields.DateTime(dump_only=True)
    started_at = fields.DateTime(allow_none=True, dump_only=True)
    finished_at = fields.DateTime(allow_none=True, dump_only=True)
    ai_result = fields.Nested(AIResultSchema, allow_none=True, dump_only=True)


class AnalysisQueueSchema(Schema):
    processing_count = fields.Integer(dump_only=True)
    queued_count = fields.Integer(dump_only=True)
    processing = fields.Nested(AnalysisJobSchema, allow_none=True, dump_only=True)
    queued = fields.List(fields.Nested(AnalysisJobSchema), dump_only=True)
    recently_finished = fields.List(fields.Nested(AnalysisJobSchema), dump_only=True)
