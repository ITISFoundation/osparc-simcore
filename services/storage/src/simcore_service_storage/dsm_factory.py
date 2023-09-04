from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

from aiohttp import web
from models_library.api_schemas_storage import LinkType, UploadedPart
from models_library.projects_nodes_io import LocationID, LocationName, StorageFileID
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize

from .models import DatasetMetaData, FileMetaData, UploadLinks


class BaseDataManager(ABC):
    @property
    def location_id(self) -> LocationID:
        """returns the location Identifier (must be unique)"""
        return self.get_location_id()

    @classmethod
    @abstractmethod
    def get_location_id(cls) -> LocationID:
        """returns the location Identifier (must be unique)"""

    @property
    def location_name(self) -> LocationName:
        """returns the location human readable name (must be unique)"""
        return self.get_location_name()

    @classmethod
    @abstractmethod
    def get_location_name(cls) -> LocationName:
        """returns the location human readable name (must be unique)"""

    @abstractmethod
    async def authorized(self, user_id: UserID) -> bool:
        """returns True if user with user_id is authorized to access the storage"""

    @abstractmethod
    async def list_datasets(self, user_id: UserID) -> list[DatasetMetaData]:
        """returns all the top level datasets a user has access to"""

    @abstractmethod
    async def list_files_in_dataset(
        self, user_id: UserID, dataset_id: str, *, expand_dirs: bool
    ) -> list[FileMetaData]:
        """returns all the file meta data inside dataset with dataset_id"""
        # NOTE: expand_dirs will be replaced by pagination in the future

    @abstractmethod
    async def list_files(
        self, user_id: UserID, *, expand_dirs: bool, uuid_filter: str = ""
    ) -> list[FileMetaData]:
        """returns all the file meta data a user has access to (uuid_filter may be used)"""
        # NOTE: expand_dirs will be replaced by pagination in the future

    @abstractmethod
    async def get_file(self, user_id: UserID, file_id: StorageFileID) -> FileMetaData:
        """returns the file meta data of file_id if user_id has the rights to"""

    @abstractmethod
    async def create_file_upload_links(
        self,
        user_id: UserID,
        file_id: StorageFileID,
        link_type: LinkType,
        file_size_bytes: ByteSize,
        *,
        is_directory: bool,
    ) -> UploadLinks:
        """creates one or more upload file links if user has the rights to, expects the client to complete/abort upload"""

    @abstractmethod
    async def complete_file_upload(
        self,
        file_id: StorageFileID,
        user_id: UserID,
        uploaded_parts: list[UploadedPart],
    ) -> FileMetaData:
        """completes an upload if the user has the rights to"""

    @abstractmethod
    async def abort_file_upload(self, user_id: UserID, file_id: StorageFileID) -> None:
        """aborts an upload if user has the rights to, and reverts
        to the latest version if available, else will delete the file"""

    @abstractmethod
    async def create_file_download_link(
        self, user_id: UserID, file_id: StorageFileID, link_type: LinkType
    ) -> AnyUrl:
        """creates a download file link if user has the rights to"""

    @abstractmethod
    async def delete_file(self, user_id: UserID, file_id: StorageFileID) -> None:
        """deletes file if user has the rights to"""


@dataclass
class DataManagerProvider:
    app: web.Application
    _builders: dict[
        LocationID,
        tuple[Callable[[web.Application], BaseDataManager], type[BaseDataManager]],
    ] = field(default_factory=dict)
    _services: list[BaseDataManager] = field(default_factory=list)

    def register_builder(
        self,
        location_id: LocationID,
        builder: Callable[[web.Application], BaseDataManager],
        dsm_type: type[BaseDataManager],
    ):
        self._builders[location_id] = (builder, dsm_type)

    def _create(self, location_id: LocationID, **kwargs) -> BaseDataManager:
        builder_and_type = self._builders.get(location_id)
        if not builder_and_type:
            raise ValueError(location_id)
        builder, _dsm_type = builder_and_type
        new_dsm = builder(self.app, **kwargs)
        self._services.append(new_dsm)
        return new_dsm

    def get(self, location_id: LocationID) -> BaseDataManager:
        for dsm in self._services:
            if dsm.location_id == location_id:
                return dsm
        # try to create it
        return self._create(location_id)

    def locations(self) -> list[LocationID]:
        return list(self._builders.keys())
