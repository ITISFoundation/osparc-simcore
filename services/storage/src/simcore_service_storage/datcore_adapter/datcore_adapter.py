from typing import List

from ..models import DatasetMetaData, FileMetaDataEx


async def list_all_datasets_files_metadatas(
    api_token: str, api_secret: str
) -> List[FileMetaDataEx]:
    pass


async def list_all_files_metadatas_in_dataset(
    api_token: str, api_secret: str, dataset_id: str
) -> List[FileMetaDataEx]:
    pass


async def list_datasets(api_token: str, api_secret: str) -> List[DatasetMetaData]:
    pass


async def get_file_metadata(
    api_token: str, api_secret: str, file_id: str
) -> FileMetaDataEx:
    pass
