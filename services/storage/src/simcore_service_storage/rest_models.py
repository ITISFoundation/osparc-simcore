""" RestAPI models

"""
import attr

from simcore_servicelib.rest_models import ErrorItemType, ErrorType, LogMessageType #pylint: disable=W0611


# NOTE: using these, optional and required fields are always transmitted!
# NOTE: make some attrs nullable by default!?

@attr.s(auto_attribs=True)
class FileMetaDataType:
    filename: str
    version: str
    last_accessed: float
    owner: str
    storage_location: str

    # TODO: from-to db_models!



#  TODO: fix __all__
