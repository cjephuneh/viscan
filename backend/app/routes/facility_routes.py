from flask.views import MethodView
from flask_smorest import Blueprint

from app.extensions import db
from app.models import Facility
from app.schemas.common import DetailSchema
from app.schemas.facility import FacilityCreateSchema, FacilitySchema

blp = Blueprint(
    "facilities",
    __name__,
    url_prefix="/api/v1/facilities",
    description="Health facility records",
)


@blp.route("/")
class FacilityList(MethodView):
    @blp.response(200, FacilitySchema(many=True))
    def get(self):
        return Facility.query.order_by(Facility.id).all()

    @blp.arguments(FacilityCreateSchema)
    @blp.response(201, FacilitySchema)
    @blp.alt_response(400, schema=DetailSchema)
    def post(self, data):
        facility = Facility(
            name=data["name"],
            type=data["type"],
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            is_active=True,
        )
        db.session.add(facility)
        db.session.commit()
        return facility
