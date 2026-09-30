from marshmallow import Schema, fields, validate


class FacilitySchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    type = fields.String(required=True, validate=validate.Length(min=1, max=64))
    latitude = fields.Float(allow_none=True, validate=validate.Range(min=-90, max=90))
    longitude = fields.Float(allow_none=True, validate=validate.Range(min=-180, max=180))
    is_active = fields.Boolean(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class FacilityCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    type = fields.String(required=True, validate=validate.Length(min=1, max=64))
    latitude = fields.Float(
        load_default=None, allow_none=True, validate=validate.Range(min=-90, max=90)
    )
    longitude = fields.Float(
        load_default=None, allow_none=True, validate=validate.Range(min=-180, max=180)
    )
