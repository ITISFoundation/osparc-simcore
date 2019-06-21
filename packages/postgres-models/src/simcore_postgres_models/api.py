# pylint: disable=unused-import

# FIXME: temporary import from other modules until all models are found. Then revert the import!
#from simcore_sdk.models import metadata as sdk_metadata  # imports pipeline stuff as well
#import simcore_service_webserver.db_models
#import simcore_service_webserver.projects

#from simcore_service_storage.models import metadata as storage_metadata

#from .tables.base import metadata
#from .tables import file_meta_data_table

#target_metadatas = [sdk_metadata, storage_metadata]

from . import storage_tables, webserver_tables
from .tables.base import metadata

target_metadatas = [metadata, ]
