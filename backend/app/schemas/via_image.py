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
    analysis_job = fields.Method("dump_analysis_job", dump_only=True, allow_none=True)
    ai_results = fields.Nested(AIResultSchema, many=True, dump_only=True)

    def build_file_url(self, obj) -> str:
        # /backend-images/ is the path that is unambiguous behind the Nginx
        # gateway (/api/v1/images/<id>/file there belongs to ai-interpreter).
        return f"/api/v1/backend-images/{obj.id}/file"

    def dump_analysis_job(self, obj):
        jobs = list(obj.analysis_jobs)
        if not jobs:
            return None
        from app.schemas.analysis_job import AnalysisJobSchema
        from app.services.queue_service import present_job

        return AnalysisJobSchema().dump(present_job(jobs[-1]))
