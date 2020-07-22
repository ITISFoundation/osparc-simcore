import bson
from marshmallow import compat as ma_compat
from marshmallow import fields as ma_fields
from umongo import fields


class BinaryField(fields.BaseField, ma_fields.Field):
    default_error_messages = {"invalid": "Not a valid byte sequence."}

    def _serialize(self, value, attr, data):
        return ma_compat.binary_type(value)

    def _deserialize(self, value, attr, data):
        if not isinstance(value, ma_compat.binary_type):
            self.fail("invalid")
        return value

    def _serialize_to_mongo(self, obj):
        return bson.binary.Binary(obj)

    def _deserialize_from_mongo(self, value):
        return bytes(value)
