""" RestAPI models

"""
from marshmallow import Schema, fields
from servicelib.rest_models import (ErrorItemType,  # pylint: disable=W0611
                                    ErrorType, LogMessageType)

# NOTE: using these, optional and required fields are always transmitted!
# NOTE: make some attrs nullable by default!?



class FileMetaDataSchema(Schema):
    filename = fields.Str()
    version = fields.Str()
    last_accessed = fields.DateTime()
    owner = fields.Str()
    storage_location = fields.Str()



#  TODO: fix __all__
