from marshmallow import Schema, fields


class DetailSchema(Schema):
    detail = fields.String(required=True)
