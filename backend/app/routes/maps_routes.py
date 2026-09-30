from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from app.schemas.common import DetailSchema
from app.schemas.integrations import DistanceQuerySchema, NearbyQuerySchema
from app.services import maps_service

blp = Blueprint(
    "maps",
    __name__,
    url_prefix="/api/v1/maps",
    description="Maps and facility proximity helpers",
)


class NearbyFacilitySchema(Schema):
    id = fields.Integer()
    name = fields.String()
    type = fields.String()
    latitude = fields.Float()
    longitude = fields.Float()
    distance_km = fields.Float()


class DistanceSchema(Schema):
    distance_km = fields.Float()
    origin = fields.Dict()
    destination = fields.Dict()
    provider = fields.String()


@blp.route("/facilities/nearby")
class NearbyFacilities(MethodView):
    @blp.arguments(NearbyQuerySchema, location="query")
    @blp.response(200, NearbyFacilitySchema(many=True))
    @blp.alt_response(400, schema=DetailSchema)
    @blp.alt_response(502, schema=DetailSchema)
    @blp.alt_response(503, schema=DetailSchema)
    def get(self, query_args):
        return maps_service.nearby_facilities(
            latitude=query_args["latitude"],
            longitude=query_args["longitude"],
            radius_km=query_args["radius_km"],
        )


@blp.route("/distance")
class Distance(MethodView):
    @blp.arguments(DistanceQuerySchema, location="query")
    @blp.response(200, DistanceSchema)
    def get(self, query_args):
        return maps_service.calculate_distance(
            origin_latitude=query_args["origin_latitude"],
            origin_longitude=query_args["origin_longitude"],
            destination_latitude=query_args["destination_latitude"],
            destination_longitude=query_args["destination_longitude"],
        )
