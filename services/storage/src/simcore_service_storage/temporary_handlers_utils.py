from models_library.api_schemas_storage import DatasetMetaDataGet, FileMetaDataGet

# NOTE: TEMPORARY UTILS (will be removed in the next PRs for refactoring storage)
from pydantic import parse_obj_as
from simcore_service_storage.models import DatasetMetaData, FileMetaDataEx


def convert_to_api_dataset(x: DatasetMetaData) -> DatasetMetaDataGet:
    return parse_obj_as(DatasetMetaDataGet, x)


def convert_to_api_fmd(x: FileMetaDataEx) -> FileMetaDataGet:
    return parse_obj_as(FileMetaDataGet, x.fmd)
