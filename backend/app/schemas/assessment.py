from marshmallow import Schema, fields, validate


class AssessmentSchema(Schema):
    id = fields.Integer(dump_only=True)
    screening_id = fields.Integer(dump_only=True)
    result = fields.String(required=True, validate=validate.Length(min=1, max=64))
    notes = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=2000))
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class AssessmentUpdateSchema(Schema):
    result = fields.String(validate=validate.Length(min=1, max=64))
    notes = fields.String(allow_none=True, validate=validate.Length(max=2000))
