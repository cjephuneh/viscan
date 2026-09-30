from marshmallow import Schema, fields, validate


class NearbyQuerySchema(Schema):
    latitude = fields.Float(required=True, validate=validate.Range(min=-90, max=90))
    longitude = fields.Float(required=True, validate=validate.Range(min=-180, max=180))
    radius_km = fields.Float(load_default=25, validate=validate.Range(min=0.1, max=200))


class DistanceQuerySchema(Schema):
    origin_latitude = fields.Float(required=True, validate=validate.Range(min=-90, max=90))
    origin_longitude = fields.Float(required=True, validate=validate.Range(min=-180, max=180))
    destination_latitude = fields.Float(required=True, validate=validate.Range(min=-90, max=90))
    destination_longitude = fields.Float(required=True, validate=validate.Range(min=-180, max=180))


class SmsSchema(Schema):
    to = fields.String(required=True, validate=validate.Regexp(r"^\+?[0-9]{8,15}$"))
    message = fields.String(required=True, validate=validate.Length(min=1, max=500))


class TranslateSchema(Schema):
    text = fields.String(required=True, validate=validate.Length(min=1, max=2000))
    source_language = fields.String(
        required=True, validate=validate.Regexp(r"^[A-Za-z]{2,8}$")
    )
    target_language = fields.String(
        required=True, validate=validate.Regexp(r"^[A-Za-z]{2,8}$")
    )


class SynthesizeSchema(Schema):
    text = fields.String(required=True, validate=validate.Length(min=1, max=2000))
    language = fields.String(
        load_default=None, allow_none=True, validate=validate.Regexp(r"^[A-Za-z]{2,8}$")
    )
