from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .models import DatasetMetaData, FileMetaDataEx


def DataStorageInterface(ABC):
    """An interface to any data storage system plugged to this service"""

    @abstractmethod
    async def is_responsive(self, session_id: str, **options) -> bool:
        """Returns True if service is available for a given session"""
        raise NotImplementedError

    # FILES resource ---

    @abstractmethod
    async def list_files(
        self, session_id: str, *, filter: Optional[Dict[str, Any]] = None
    ) -> List[FileMetaDataEx]:
        """Lists all files of a given session"""
        # TODO: pagination
        raise NotImplementedError

    @abstractmethod
    async def get_file(self, session_id: str, file_id: str) -> Optional[FileMetaDataEx]:
        raise NotImplementedError

    @abstractmethod
    async def delete_file(self, session_id: str, file_id: str) -> None:
        raise NotImplementedError

    # DATASET resource ---
    #  - a group of files and its metadata?

    @abstractmethod
    async def list_datasets(self, session_id: str) -> List[DatasetMetaData]:
        raise NotImplementedError

    @abstractmethod
    async def get_dataset(
        self, session_id: str, dataset_id: str
    ) -> List[FileMetaDataEx]:
        raise NotImplementedError
