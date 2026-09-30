from flask.views import MethodView
from flask_smorest import Blueprint

from app.errors import APIError
from app.extensions import db
from app.models.analysis_job import AnalysisJob
from app.schemas.analysis_job import AnalysisJobSchema, AnalysisQueueSchema
from app.schemas.common import DetailSchema
from app.services.queue_service import build_queue_view, present_job

blp = Blueprint(
    "analysis_queue",
    __name__,
    url_prefix="/api/v1",
    description=(
        "VIA analysis queue. One image is analyzed at a time. "
        "Further uploads stay queued until the current image finishes."
    ),
)


@blp.route("/analysis-queue/")
class AnalysisQueue(MethodView):
    @blp.response(200, AnalysisQueueSchema)
    def get(self):
        """Show the image being analyzed, the images waiting, and recent results."""
        return build_queue_view()


@blp.route("/analysis-jobs/<int:job_id>/")
class AnalysisJobDetail(MethodView):
    @blp.response(200, AnalysisJobSchema)
    @blp.alt_response(404, schema=DetailSchema)
    def get(self, job_id):
        """Poll one queued image until it is completed or failed."""
        job = db.session.get(AnalysisJob, job_id)
        if job is None:
            raise APIError("Analysis job not found.", 404)
        return present_job(job)
