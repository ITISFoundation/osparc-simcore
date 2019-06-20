# FIXME: temporary import from other modules until all models are found. Then revert the import!

from simcore_sdk.models import metadata as sdk_metadata  # imports pipeline stuff as well
import simcore_service_webserver.db_models
import simcore_service_webserver.projects

from simcore_service_storage.models import metadata as storage_metadata


target_metadatas = [sdk_metadata, storage_metadata]
