import contextlib
import datetime
import logging
import tempfile
import urllib.parse
from collections.abc import Coroutine
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from aws_library.s3 import (
    CopiedBytesTransferredCallback,
    S3DirectoryMetaData,
    S3KeyNotFoundError,
    S3MetaData,
    UploadedBytesTransferredCallback,
    UploadID,
)
from aws_library.s3._models import S3ObjectKey
from fastapi import FastAPI
from models_library.api_schemas_storage.export_data_async_jobs import AccessRightError
from models_library.api_schemas_storage.storage_schemas import (
    UNDEFINED_SIZE,
    UNDEFINED_SIZE_TYPE,
    LinkType,
    S3BucketName,
    UploadedPart,
)
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes_io import (
    LocationID,
    NodeID,
    SimcoreS3FileID,
    StorageFileID,
)
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize, NonNegativeInt, TypeAdapter, ValidationError
from servicelib.fastapi.client_session import get_client_session
from servicelib.logging_utils import log_context
from servicelib.progress_bar import ProgressBarData
from servicelib.utils import ensure_ends_with, limited_gather
from simcore_postgres_database.utils_projects import ProjectsRepo
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.ext.asyncio import AsyncEngine

from .constants import (
    DATCORE_ID,
    EXPAND_DIR_MAX_ITEM_COUNT,
    MAX_CONCURRENT_S3_TASKS,
    MAX_LINK_CHUNK_BYTE_SIZE,
    S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID,
    SIMCORE_S3_ID,
    SIMCORE_S3_STR,
)
from .core.settings import get_application_settings
from .dsm_factory import BaseDataManager
from .exceptions.errors import (
    FileAccessRightError,
    FileMetaDataNotFoundError,
    LinkAlreadyExistsError,
    ProjectAccessRightError,
    ProjectNotFoundError,
    SelectionNotAllowedError,
)
from .models import (
    DatasetMetaData,
    FileMetaData,
    FileMetaDataAtDB,
    GenericCursor,
    PathMetaData,
    TotalNumber,
    UploadLinks,
    UserOrProjectFilter,
)
from .modules.datcore_adapter import datcore_adapter
from .modules.db import get_db_engine
from .modules.db.access_layer import AccessLayerRepository
from .modules.db.file_meta_data import FileMetaDataRepository
from .modules.db.projects import ProjectRepository
from .modules.db.tokens import TokenRepository
from .modules.s3 import get_s3_client
from .utils.s3_utils import S3TransferDataCB
from .utils.simcore_s3_dsm_utils import (
    UserSelectionStr,
    compute_file_id_prefix,
    create_and_upload_export,
    create_random_export_name,
    ensure_user_selection_from_same_base_directory,
    expand_directory,
    get_accessible_project_ids,
    get_directory_file_id,
    list_child_paths_from_repository,
    list_child_paths_from_s3,
)
from .utils.utils import (
    convert_db_to_model,
    download_to_file_or_raise,
    is_file_entry_valid,
    is_valid_managed_multipart_upload,
)

_NO_CONCURRENCY: Final[int] = 1
_MAX_PARALLEL_S3_CALLS: Final[NonNegativeInt] = 10

_logger = logging.getLogger(__name__)


async def _add_frontend_needed_data(
    engine: AsyncEngine,
    *,
    project_ids: list[ProjectID],
    data: list[FileMetaData],
) -> list[FileMetaData]:
    # artifically fills ['project_name', 'node_name', 'file_id', 'raw_file_path', 'display_file_path']
    #   with information from the projects table!
    # NOTE: This part with the projects, should be done in the client code not here!

    repo = ProjectRepository.instance(engine)
    valid_project_uuids = [
        proj_data.uuid
        async for proj_data in repo.list_valid_projects_in(project_uuids=project_ids)
    ]

    prj_names_mapping = await repo.get_project_id_and_node_id_to_names_map(
        project_uuids=valid_project_uuids
    )

    clean_data: list[FileMetaData] = []
    for d in data:
        if d.project_id not in prj_names_mapping:
            continue
        assert d.project_id  # nosec
        names_mapping = prj_names_mapping[d.project_id]
        d.project_name = names_mapping[f"{d.project_id}"]
        if d.node_id in names_mapping:
            assert d.node_id  # nosec
            d.node_name = names_mapping[f"{d.node_id}"]
        if d.node_name and d.project_name:
            clean_data.append(d)

    return clean_data


@dataclass
class SimcoreS3DataManager(BaseDataManager):  # pylint:disable=too-many-public-methods
    simcore_bucket_name: S3BucketName
    app: FastAPI

    @classmethod
    def get_location_id(cls) -> LocationID:
        return SIMCORE_S3_ID

    @classmethod
    def get_location_name(cls) -> str:
        return SIMCORE_S3_STR

    async def authorized(self, _user_id: UserID) -> bool:
        return True  # always true for now

    async def list_datasets(self, user_id: UserID) -> list[DatasetMetaData]:
        readable_projects_ids = await AccessLayerRepository.instance(
            get_db_engine(self.app)
        ).get_readable_project_ids(user_id=user_id)

        return [
            DatasetMetaData(
                dataset_id=prj_data.uuid,
                display_name=prj_data.name,
            )
            async for prj_data in ProjectRepository.instance(
                get_db_engine(self.app)
            ).list_valid_projects_in(project_uuids=readable_projects_ids)
        ]

    async def list_files_in_dataset(
        self, user_id: UserID, dataset_id: str, *, expand_dirs: bool
    ) -> list[FileMetaData]:
        # NOTE: expand_dirs will be replaced by pagination in the future
        data: list[FileMetaData] = await self.list_files(
            user_id,
            expand_dirs=expand_dirs,
            uuid_filter=ensure_ends_with(dataset_id, "/"),
            project_id=None,
        )
        return data

    async def list_paths(
        self,
        user_id: UserID,
        *,
        file_filter: Path | None,
        cursor: GenericCursor | None,
        limit: NonNegativeInt,
    ) -> tuple[list[PathMetaData], GenericCursor | None, TotalNumber | None]:
        """returns a page of the file meta data a user has access to"""

        next_cursor: GenericCursor | None = None
        total: TotalNumber | None = None
        # if we have a file_filter, that means that we have potentially a project ID
        project_id = None
        with contextlib.suppress(ValueError):
            # NOTE: we currently do not support anything else than project_id/node_id/file_path here, sorry chap
            project_id = ProjectID(file_filter.parts[0]) if file_filter else None

        accessible_projects_ids = await get_accessible_project_ids(
            get_db_engine(self.app), user_id=user_id, project_id=project_id
        )

        # check if the file_filter is a directory or inside one
        dir_fmd = None
        if file_filter:
            dir_fmd = await FileMetaDataRepository.instance(
                get_db_engine(self.app)
            ).try_get_directory(file_filter=file_filter)

        if dir_fmd:
            # NOTE: files are not listed in the DB but in S3 only
            assert file_filter  # nosec
            assert project_id  # nosec
            (paths_metadata, next_cursor) = await list_child_paths_from_s3(
                get_s3_client(self.app),
                dir_fmd=dir_fmd,
                bucket=self.simcore_bucket_name,
                file_filter=file_filter,
                limit=limit,
                cursor=cursor,
            )
        else:
            # NOTE: files are DB-based
            (
                paths_metadata,
                next_cursor,
                total,
            ) = await list_child_paths_from_repository(
                get_db_engine(self.app),
                filter_by_project_ids=accessible_projects_ids,
                filter_by_file_prefix=file_filter,
                limit=limit,
                cursor=cursor,
            )

        # extract the returned project_ids
        project_ids = list(
            {path.project_id for path in paths_metadata if path.project_id is not None}
        )

        ids_names_map = await ProjectRepository.instance(
            get_db_engine(self.app)
        ).get_project_id_and_node_id_to_names_map(project_uuids=project_ids)

        for path in paths_metadata:
            if path.project_id is not None:
                id_name_map = ids_names_map.get(path.project_id, {})
                path.update_display_fields(id_name_map)

        return paths_metadata, next_cursor, total

    async def compute_path_size(self, user_id: UserID, *, path: Path) -> ByteSize:
        """returns the total size of an arbitrary path"""
        # check access rights first
        project_id = None
        with contextlib.suppress(ValueError):
            # NOTE: we currently do not support anything else than project_id/node_id/file_path here, sorry chap
            project_id = ProjectID(path.parts[0])

        accessible_projects_ids = await get_accessible_project_ids(
            get_db_engine(self.app), user_id=user_id, project_id=project_id
        )

        # use-cases:
        # 1. path is not a valid StorageFileID (e.g. a project or project/node) --> all entries are in the DB (files and folder)
        #   2. path is valid StorageFileID and not in the DB --> entries are only in S3
        #   3. path is valid StorageFileID and in the DB --> return directly from the DB

        use_db_data = True
        with contextlib.suppress(ValidationError):
            file_id: StorageFileID = TypeAdapter(StorageFileID).validate_python(
                f"{path}"
            )
            # path is a valid StorageFileID

            if (
                dir_fmd := await FileMetaDataRepository.instance(
                    get_db_engine(self.app)
                ).try_get_directory(file_filter=path)
            ) and dir_fmd.file_id != file_id:
                # this is pure S3 aka use-case 2
                use_db_data = False

        if not use_db_data:
            assert file_id  # nosec
            s3_metadata = await get_s3_client(self.app).get_directory_metadata(
                bucket=self.simcore_bucket_name, prefix=file_id
            )
            assert s3_metadata.size  # nosec
            return s3_metadata.size

        # all other use-cases are in the DB
        fmds = await FileMetaDataRepository.instance(
            get_db_engine(self.app)
        ).list_filter_with_partial_file_id(
            user_or_project_filter=UserOrProjectFilter(
                user_id=user_id, project_ids=accessible_projects_ids
            ),
            file_id_prefix=f"{path}",
            partial_file_id=None,
            sha256_checksum=None,
            is_directory=None,
        )

        # ensure file sizes are uptodate
        updated_fmds = []
        for metadata in fmds:
            if is_file_entry_valid(metadata):
                updated_fmds.append(convert_db_to_model(metadata))
                continue
            updated_fmds.append(
                convert_db_to_model(await self._update_database_from_storage(metadata))
            )

        return ByteSize(sum(fmd.file_size for fmd in updated_fmds))

    async def list_files(
        self,
        user_id: UserID,
        *,
        expand_dirs: bool,
        uuid_filter: str,
        project_id: ProjectID | None,
    ) -> list[FileMetaData]:
        """
        expand_dirs `False`: returns one metadata entry for each directory
        expand_dirs `True`: returns all files in each directory (no directories will be included)
        project_id: If passed, only list files associated with that project_id
        uuid_filter: If passed, only list files whose 'object_name' match (ilike) the passed string

        NOTE: expand_dirs will be replaced by pagination in the future
        currently only {EXPAND_DIR_MAX_ITEM_COUNT} items will be returned
        The endpoint produces similar results to what it did previously
        """

        data: list[FileMetaData] = []
        accessible_projects_ids = []
        uid: UserID | None = None
        access_layer_repo = AccessLayerRepository.instance(get_db_engine(self.app))
        if project_id is not None:
            project_access_rights = await access_layer_repo.get_project_access_rights(
                user_id=user_id, project_id=project_id
            )
            if not project_access_rights.read:
                raise ProjectAccessRightError(
                    access_right="read", project_id=project_id
                )
            accessible_projects_ids = [project_id]
            uid = None
        else:
            accessible_projects_ids = await access_layer_repo.get_readable_project_ids(
                user_id=user_id
            )
            uid = user_id
        file_and_directory_meta_data = await FileMetaDataRepository.instance(
            get_db_engine(self.app)
        ).list_filter_with_partial_file_id(
            user_or_project_filter=UserOrProjectFilter(
                user_id=uid, project_ids=accessible_projects_ids
            ),
            file_id_prefix=None,
            is_directory=None,
            partial_file_id=uuid_filter,
            sha256_checksum=None,
        )

        # add all the entries from file_meta_data without
        for metadata in file_and_directory_meta_data:
            # below checks ensures that directoris either appear as
            if metadata.is_directory and expand_dirs:
                # avoids directory files and does not add any directory entry to the result
                continue

            if is_file_entry_valid(metadata):
                data.append(convert_db_to_model(metadata))
                continue
            with suppress(S3KeyNotFoundError):
                updated_fmd = await self._update_database_from_storage(metadata)
                data.append(convert_db_to_model(updated_fmd))

        # expand directories until the max number of files to return is reached
        directory_expands: list[Coroutine] = []
        for metadata in file_and_directory_meta_data:
            if (
                expand_dirs
                and metadata.is_directory
                and len(data) < EXPAND_DIR_MAX_ITEM_COUNT
            ):
                max_items_to_include = EXPAND_DIR_MAX_ITEM_COUNT - len(data)
                directory_expands.append(
                    expand_directory(
                        get_s3_client(self.app),
                        self.simcore_bucket_name,
                        metadata,
                        max_items_to_include,
                    )
                )
        for files_in_directory in await limited_gather(
            *directory_expands, limit=_MAX_PARALLEL_S3_CALLS
        ):
            data.extend(files_in_directory)

        return await _add_frontend_needed_data(
            get_db_engine(self.app), project_ids=accessible_projects_ids, data=data
        )

    async def get_file(self, user_id: UserID, file_id: StorageFileID) -> FileMetaData:
        can = await AccessLayerRepository.instance(
            get_db_engine(self.app)
        ).get_file_access_rights(user_id=user_id, file_id=file_id)
        if not can.read:
            raise FileAccessRightError(access_right="read", file_id=file_id)

        fmd = await FileMetaDataRepository.instance(get_db_engine(self.app)).get(
            file_id=TypeAdapter(SimcoreS3FileID).validate_python(file_id)
        )
        if is_file_entry_valid(fmd):
            return convert_db_to_model(fmd)
        # get file from storage if available
        fmd = await self._update_database_from_storage(fmd)
        return convert_db_to_model(fmd)

    async def can_read_file(self, user_id: UserID, file_id: StorageFileID):
        can = await AccessLayerRepository.instance(
            get_db_engine(self.app)
        ).get_file_access_rights(user_id=user_id, file_id=file_id)
        if not can.read:
            raise FileAccessRightError(access_right="read", file_id=file_id)

    async def create_file_upload_links(
        self,
        user_id: UserID,
        file_id: StorageFileID,
        link_type: LinkType,
        file_size_bytes: ByteSize,
        *,
        sha256_checksum: SHA256Str | None,
        is_directory: bool,
    ) -> UploadLinks:
        can = await AccessLayerRepository.instance(
            get_db_engine(self.app)
        ).get_file_access_rights(user_id=user_id, file_id=file_id)
        if not can.write:
            raise FileAccessRightError(access_right="write", file_id=file_id)

        # NOTE: if this gets called successively with the same file_id, and
        # there was a multipart upload in progress beforehand, it MUST be
        # cancelled to prevent unwanted costs in AWS
        await self._clean_pending_upload(
            TypeAdapter(SimcoreS3FileID).validate_python(file_id)
        )

        if (
            not is_directory
        ):  # NOTE: Delete is not needed for directories that are synced via an external tool (rclone/aws s3 cli).
            # ensure file is deleted first in case it already exists
            # https://github.com/ITISFoundation/osparc-simcore/pull/5108
            await self.delete_file(
                user_id=user_id,
                file_id=file_id,
                # NOTE: bypassing check since the project access rights don't play well
                # with collaborators
                # SEE https://github.com/ITISFoundation/osparc-simcore/issues/5159
                enforce_access_rights=False,
            )
        # initiate the file meta data table
        fmd = await self._create_fmd_for_upload(
            user_id,
            file_id,
            upload_id=(
                S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID
                if (
                    get_s3_client(self.app).is_multipart(file_size_bytes)
                    or link_type == LinkType.S3
                )
                else None
            ),
            is_directory=is_directory,
            sha256_checksum=sha256_checksum,
        )

        if link_type == LinkType.PRESIGNED and get_s3_client(self.app).is_multipart(
            file_size_bytes
        ):
            # create multipart links
            with log_context(
                logger=_logger,
                level=logging.DEBUG,
                msg=f"Creating multipart upload links for {file_id=}",
            ):
                assert file_size_bytes  # nosec
                multipart_presigned_links = await get_s3_client(
                    self.app
                ).create_multipart_upload_links(
                    bucket=fmd.bucket_name,
                    object_key=fmd.file_id,
                    file_size=file_size_bytes,
                    expiration_secs=get_application_settings(
                        self.app
                    ).STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS,
                    sha256_checksum=fmd.sha256_checksum,
                )
            # update the database so we keep the upload id
            fmd.upload_id = multipart_presigned_links.upload_id
            await FileMetaDataRepository.instance(get_db_engine(self.app)).upsert(
                fmd=fmd
            )
            return UploadLinks(
                multipart_presigned_links.urls,
                multipart_presigned_links.chunk_size,
            )
        if link_type == LinkType.PRESIGNED:
            # create single presigned link
            with log_context(
                logger=_logger,
                level=logging.DEBUG,
                msg=f"Creating single presigned upload link for {file_id=}",
            ):
                single_presigned_link = await get_s3_client(
                    self.app
                ).create_single_presigned_upload_link(
                    bucket=self.simcore_bucket_name,
                    object_key=fmd.file_id,
                    expiration_secs=get_application_settings(
                        self.app
                    ).STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS,
                )
            return UploadLinks(
                [single_presigned_link],
                file_size_bytes or MAX_LINK_CHUNK_BYTE_SIZE[link_type],
            )

        # user wants just the s3 link
        with log_context(
            logger=_logger,
            level=logging.DEBUG,
            msg=f"Compute S3 link for file_id={file_id}",
        ):
            s3_link = get_s3_client(self.app).compute_s3_url(
                bucket=self.simcore_bucket_name,
                object_key=TypeAdapter(SimcoreS3FileID).validate_python(file_id),
            )
        return UploadLinks(
            [s3_link], file_size_bytes or MAX_LINK_CHUNK_BYTE_SIZE[link_type]
        )

    async def abort_file_upload(
        self,
        user_id: UserID,
        file_id: StorageFileID,
    ) -> None:
        can = await AccessLayerRepository.instance(
            get_db_engine(self.app)
        ).get_file_access_rights(user_id=user_id, file_id=file_id)
        if not can.delete or not can.write:
            raise FileAccessRightError(access_right="write/delete", file_id=file_id)

        fmd = await FileMetaDataRepository.instance(get_db_engine(self.app)).get(
            file_id=TypeAdapter(SimcoreS3FileID).validate_python(file_id)
        )
        if is_valid_managed_multipart_upload(fmd.upload_id):
            assert fmd.upload_id  # nosec
            await get_s3_client(self.app).abort_multipart_upload(
                bucket=fmd.bucket_name,
                object_key=fmd.file_id,
                upload_id=fmd.upload_id,
            )
        # try to recover a file if it existed
        with contextlib.suppress(S3KeyNotFoundError):
            await get_s3_client(self.app).undelete_object(
                bucket=fmd.bucket_name, object_key=fmd.file_id
            )

        try:
            # try to revert to what we had in storage if any
            await self._update_database_from_storage(fmd)
        except S3KeyNotFoundError:
            # the file does not exist, so we delete the entry in the db
            await FileMetaDataRepository.instance(get_db_engine(self.app)).delete(
                file_ids=[fmd.file_id]
            )

    async def complete_file_upload(
        self,
        file_id: StorageFileID,
        user_id: UserID,
        uploaded_parts: list[UploadedPart],
    ) -> FileMetaData:
        can = await AccessLayerRepository.instance(
            get_db_engine(self.app)
        ).get_file_access_rights(user_id=user_id, file_id=file_id)
        if not can.write:
            raise FileAccessRightError(access_right="write", file_id=file_id)
        fmd = await FileMetaDataRepository.instance(get_db_engine(self.app)).get(
            file_id=TypeAdapter(SimcoreS3FileID).validate_python(file_id)
        )

        if is_valid_managed_multipart_upload(fmd.upload_id):
            # NOTE: Processing of a Complete Multipart Upload request
            # could take several minutes to complete. After Amazon S3
            # begins processing the request, it sends an HTTP response
            # header that specifies a 200 OK response. While processing
            # is in progress, Amazon S3 periodically sends white space
            # characters to keep the connection from timing out. Because
            # a request could fail after the initial 200 OK response
            # has been sent, it is important that you check the response
            # body to determine whether the request succeeded.
            assert fmd.upload_id  # nosec
            await get_s3_client(self.app).complete_multipart_upload(
                bucket=self.simcore_bucket_name,
                object_key=fmd.file_id,
                upload_id=fmd.upload_id,
                uploaded_parts=uploaded_parts,
            )
        fmd = await self._update_database_from_storage(fmd)
        assert fmd  # nosec
        return convert_db_to_model(fmd)

    async def create_file_download_link(
        self, user_id: UserID, file_id: StorageFileID, link_type: LinkType
    ) -> AnyUrl:
        """
        Cases:
        1. the file_id maps 1:1 to `file_meta_data` (e.g. it is not a file inside a directory)
        2. the file_id represents a file inside a directory (its root path maps 1:1 to a `file_meta_data` defined as a directory)

        3. Raises FileNotFoundError if the file does not exist
        4. Raises FileAccessRightError if the user does not have access to the file
        """
        directory_file_id = await get_directory_file_id(
            get_db_engine(self.app), file_id
        )
        can = await AccessLayerRepository.instance(
            get_db_engine(self.app)
        ).get_file_access_rights(
            user_id=user_id, file_id=directory_file_id if directory_file_id else file_id
        )
        if not can.read:
            # NOTE: this is tricky. A user with read access can download and data!
            # If write permission would be required, then shared projects as views cannot
            # recover data in nodes (e.g. jupyter cannot pull work data)
            #
            raise FileAccessRightError(
                access_right="read",
                file_id=directory_file_id if directory_file_id else file_id,
            )
        if directory_file_id:
            if not await get_s3_client(self.app).object_exists(
                bucket=self.simcore_bucket_name, object_key=f"{file_id}"
            ):
                raise S3KeyNotFoundError(key=file_id, bucket=self.simcore_bucket_name)
            return await self._get_link(
                TypeAdapter(SimcoreS3FileID).validate_python(file_id), link_type
            )
        # standard file link
        fmd = await FileMetaDataRepository.instance(get_db_engine(self.app)).get(
            file_id=TypeAdapter(SimcoreS3FileID).validate_python(file_id)
        )
        if not is_file_entry_valid(fmd):
            # try lazy update
            fmd = await self._update_database_from_storage(fmd)
        return await self._get_link(fmd.object_name, link_type)

    async def _get_link(
        self, s3_file_id: SimcoreS3FileID, link_type: LinkType
    ) -> AnyUrl:
        link: AnyUrl = TypeAdapter(AnyUrl).validate_python(
            f"s3://{self.simcore_bucket_name}/{urllib.parse.quote(s3_file_id)}"
        )
        if link_type == LinkType.PRESIGNED:
            link = await get_s3_client(self.app).create_single_presigned_download_link(
                bucket=self.simcore_bucket_name,
                object_key=s3_file_id,
                expiration_secs=get_application_settings(
                    self.app
                ).STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS,
            )

        return link

    async def delete_file(
        self,
        user_id: UserID,
        file_id: StorageFileID,
        *,
        enforce_access_rights: bool = True,
    ):
        #   _   _  ___ _____ _____
        #  | \ | |/ _ \_   _| ____|
        #  |  \| | | | || | |  _|
        #  | |\  | |_| || | | |___
        #  |_| \_|\___/ |_| |_____|
        # NOTE: (a very big one)
        # `enforce_access_rights` is set to False because permissions are based on "project access rights"
        # they should be based on data access rights (which is currently not present)
        # Only use this in those circumstances where a collaborator requires to delete a file (the current
        # permissions model will not allow him to do so, even though this is a legitimate action)
        # SEE https://github.com/ITISFoundation/osparc-simcore/issues/5159
        with log_context(
            logger=_logger, level=logging.DEBUG, msg=f"Deleting file {file_id=}"
        ):
            if enforce_access_rights:
                can = await AccessLayerRepository.instance(
                    get_db_engine(self.app)
                ).get_file_access_rights(user_id=user_id, file_id=file_id)
                if not can.delete:
                    raise FileAccessRightError(access_right="delete", file_id=file_id)

            try:
                await get_s3_client(self.app).delete_objects_recursively(
                    bucket=self.simcore_bucket_name,
                    prefix=file_id,
                )
            except S3KeyNotFoundError:
                _logger.warning("File %s not found in S3", file_id)
                # we still need to clean up the database entry (it exists)
                # and to invalidate the size of the parent directory

            async with transaction_context(get_db_engine(self.app)) as connection:
                file_meta_data_repo = FileMetaDataRepository.instance(
                    get_db_engine(self.app)
                )
                await file_meta_data_repo.delete(
                    connection=connection, file_ids=[file_id]
                )

                if parent_dir_fmds := await file_meta_data_repo.list_filter_with_partial_file_id(
                    connection=connection,
                    user_or_project_filter=UserOrProjectFilter(
                        user_id=user_id, project_ids=[]
                    ),
                    file_id_prefix=compute_file_id_prefix(file_id, 2),
                    partial_file_id=None,
                    is_directory=True,
                    sha256_checksum=None,
                ):
                    parent_dir_fmd = max(
                        parent_dir_fmds, key=lambda fmd: len(fmd.file_id)
                    )
                    parent_dir_fmd.file_size = UNDEFINED_SIZE
                    await file_meta_data_repo.upsert(
                        connection=connection, fmd=parent_dir_fmd
                    )

    async def delete_project_simcore_s3(
        self, user_id: UserID, project_id: ProjectID, node_id: NodeID | None = None
    ) -> None:
        can = await AccessLayerRepository.instance(
            get_db_engine(self.app)
        ).get_project_access_rights(user_id=user_id, project_id=project_id)
        if not can.delete:
            raise ProjectAccessRightError(access_right="delete", project_id=project_id)

        if not node_id:
            await FileMetaDataRepository.instance(
                get_db_engine(self.app)
            ).delete_all_from_project(project_id=project_id)
        else:
            await FileMetaDataRepository.instance(
                get_db_engine(self.app)
            ).delete_all_from_node(node_id=node_id)

        await get_s3_client(self.app).delete_objects_recursively(
            bucket=self.simcore_bucket_name,
            prefix=ensure_ends_with(
                f"{project_id}/{node_id}" if node_id else f"{project_id}", "/"
            ),
        )

    async def deep_copy_project_simcore_s3(
        self,
        user_id: UserID,
        src_project: dict[str, Any],
        dst_project: dict[str, Any],
        node_mapping: dict[NodeID, NodeID],
        task_progress: ProgressBarData,
    ) -> None:
        src_project_uuid = ProjectID(src_project["uuid"])
        dst_project_uuid = ProjectID(dst_project["uuid"])
        with log_context(
            _logger,
            logging.INFO,
            msg=f"{src_project_uuid} -> {dst_project_uuid}: "
            "Step 1: check access rights (read of src and write of dst)",
        ):
            task_progress.description = "Checking study access rights..."

            for prj_uuid in [src_project_uuid, dst_project_uuid]:
                if not await ProjectsRepo(get_db_engine(self.app)).exists(
                    project_uuid=prj_uuid
                ):
                    raise ProjectNotFoundError(project_id=prj_uuid)
            source_access_rights = await AccessLayerRepository.instance(
                get_db_engine(self.app)
            ).get_project_access_rights(user_id=user_id, project_id=src_project_uuid)
            dest_access_rights = await AccessLayerRepository.instance(
                get_db_engine(self.app)
            ).get_project_access_rights(user_id=user_id, project_id=dst_project_uuid)
            if not source_access_rights.read:
                raise ProjectAccessRightError(
                    access_right="read", project_id=src_project_uuid
                )
            if not dest_access_rights.write:
                raise ProjectAccessRightError(
                    access_right="write", project_id=dst_project_uuid
                )

        with log_context(
            _logger,
            logging.INFO,
            msg=f"{src_project_uuid} -> {dst_project_uuid}:"
            " Step 2: collect what to copy",
        ):
            task_progress.description = (
                f"Collecting files of '{src_project['name']}'..."
            )

            src_project_files = await FileMetaDataRepository.instance(
                get_db_engine(self.app)
            ).list_fmds(project_ids=[src_project_uuid])

            with log_context(
                _logger,
                logging.INFO,
                f"{src_project_uuid} -> {dst_project_uuid}: get total file size for "
                f"{len(src_project_files)} files",
                log_duration=True,
            ):
                sizes_and_num_files: list[
                    tuple[ByteSize | UNDEFINED_SIZE_TYPE, int]
                ] = await limited_gather(
                    *[self._get_size_and_num_files(fmd) for fmd in src_project_files],
                    limit=_MAX_PARALLEL_S3_CALLS,
                )
            total_num_of_files = sum(n for _, n in sizes_and_num_files)
            src_project_total_data_size = TypeAdapter(ByteSize).validate_python(
                sum(n for n, _ in sizes_and_num_files)
            )

        async with S3TransferDataCB(
            task_progress,
            src_project_total_data_size,
            task_progress_message_prefix=f"Copying {total_num_of_files} files to '{dst_project['name']}'",
        ) as s3_transfered_data_cb:
            with log_context(
                _logger,
                logging.INFO,
                msg=f"{src_project_uuid} -> {dst_project_uuid}:"
                " Step 3.1: prepare copy tasks for files referenced from simcore",
            ):
                copy_tasks = []
                for src_fmd in src_project_files:
                    if not src_fmd.node_id or (src_fmd.location_id != self.location_id):
                        msg = (
                            "This is not foreseen, stem from old decisions, and needs to "
                            f"be implemented if needed. Faulty metadata: {src_fmd=}"
                        )
                        raise NotImplementedError(msg)

                    if new_node_id := node_mapping.get(src_fmd.node_id):
                        copy_tasks.append(
                            self._copy_path_s3_s3(
                                user_id,
                                src_fmd=src_fmd,
                                dst_file_id=TypeAdapter(
                                    SimcoreS3FileID
                                ).validate_python(
                                    f"{dst_project_uuid}/{new_node_id}/{src_fmd.object_name.split('/', maxsplit=2)[-1]}"
                                ),
                                bytes_transfered_cb=s3_transfered_data_cb.copy_transfer_cb,
                            )
                        )
            with log_context(
                _logger,
                logging.INFO,
                msg=f"{src_project_uuid} -> {dst_project_uuid}:"
                " Step 3.1: prepare copy tasks for files referenced from DAT-CORE",
            ):
                for node_id, node in dst_project.get("workbench", {}).items():
                    copy_tasks.extend(
                        [
                            self._copy_file_datcore_s3(
                                user_id=user_id,
                                source_uuid=output["path"],
                                dest_project_id=dst_project_uuid,
                                dest_node_id=NodeID(node_id),
                                file_storage_link=output,
                                bytes_transfered_cb=s3_transfered_data_cb.upload_transfer_cb,
                            )
                            for output in node.get("outputs", {}).values()
                            if isinstance(output, dict)
                            and (
                                int(output.get("store", self.location_id)) == DATCORE_ID
                            )
                        ]
                    )
            with log_context(
                _logger,
                logging.INFO,
                msg=f"{src_project_uuid} -> {dst_project_uuid}: Step 3.3: effective copying {len(copy_tasks)} files",
            ):
                await limited_gather(*copy_tasks, limit=MAX_CONCURRENT_S3_TASKS)

    async def _get_size_and_num_files(
        self, fmd: FileMetaDataAtDB
    ) -> tuple[ByteSize | UNDEFINED_SIZE_TYPE, int]:
        if not fmd.is_directory:
            return fmd.file_size, 1

        # in case of directory list files and return size
        total_size: int = 0
        total_num_s3_objects = 0
        async for s3_objects in get_s3_client(self.app).list_objects_paginated(
            bucket=self.simcore_bucket_name,
            prefix=(
                ensure_ends_with(f"{fmd.object_name}", "/")
                if fmd.is_directory
                else fmd.object_name
            ),
        ):
            total_size += sum(x.size for x in s3_objects)
            total_num_s3_objects += len(s3_objects)

        return TypeAdapter(ByteSize).validate_python(total_size), total_num_s3_objects

    async def search_owned_files(
        self,
        *,
        user_id: UserID,
        file_id_prefix: str | None,
        sha256_checksum: SHA256Str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[FileMetaData]:
        file_metadatas = await FileMetaDataRepository.instance(
            get_db_engine(self.app)
        ).list_filter_with_partial_file_id(
            user_or_project_filter=UserOrProjectFilter(user_id=user_id, project_ids=[]),
            file_id_prefix=file_id_prefix,
            partial_file_id=None,
            is_directory=False,
            sha256_checksum=sha256_checksum,
            limit=limit,
            offset=offset,
        )
        resolved_fmds = []
        for fmd in file_metadatas:
            if is_file_entry_valid(fmd):
                resolved_fmds.append(convert_db_to_model(fmd))
                continue
            with suppress(S3KeyNotFoundError):
                updated_fmd = await self._update_database_from_storage(fmd)
                resolved_fmds.append(convert_db_to_model(updated_fmd))
        return resolved_fmds

    async def create_soft_link(
        self, user_id: int, target_file_id: StorageFileID, link_file_id: StorageFileID
    ) -> FileMetaData:
        file_meta_data_repo = FileMetaDataRepository.instance(get_db_engine(self.app))
        if await file_meta_data_repo.exists(
            file_id=TypeAdapter(SimcoreS3FileID).validate_python(link_file_id)
        ):
            raise LinkAlreadyExistsError(file_id=link_file_id)
        # validate target_uuid
        target = await self.get_file(user_id, target_file_id)
        # duplicate target and change the following columns:
        target.file_uuid = link_file_id
        target.file_id = link_file_id  # NOTE: api-server relies on this id
        target.is_soft_link = True

        return convert_db_to_model(await file_meta_data_repo.insert(fmd=target))

    async def _clean_pending_upload(self, file_id: SimcoreS3FileID) -> None:
        with log_context(
            logger=_logger,
            level=logging.DEBUG,
            msg=f"Cleaning pending uploads for {file_id=}",
        ):
            with suppress(FileMetaDataNotFoundError):
                fmd = await FileMetaDataRepository.instance(
                    get_db_engine(self.app)
                ).get(file_id=file_id)
                if is_valid_managed_multipart_upload(fmd.upload_id):
                    assert fmd.upload_id  # nosec
                    await get_s3_client(self.app).abort_multipart_upload(
                        bucket=self.simcore_bucket_name,
                        object_key=file_id,
                        upload_id=fmd.upload_id,
                    )

    async def _clean_expired_uploads(self) -> None:
        """this method will check for all incomplete updates by checking
        the upload_expires_at entry in file_meta_data table.
        1. will try to update the entry from S3 backend if exists
        2. will delete the entry if nothing exists in S3 backend.
        """
        now = datetime.datetime.utcnow()

        list_of_expired_uploads = await FileMetaDataRepository.instance(
            get_db_engine(self.app)
        ).list_fmds(expired_after=now)

        if not list_of_expired_uploads:
            return
        _logger.debug(
            "found following expired uploads: [%s]",
            [fmd.file_id for fmd in list_of_expired_uploads],
        )

        # try first to upload these from S3, they might have finished and the client forgot to tell us (conservative)
        # NOTE: no concurrency here as we want to run low resources
        updated_fmds = await limited_gather(
            *(
                self._update_database_from_storage(fmd)
                for fmd in list_of_expired_uploads
            ),
            reraise=False,
            log=_logger,
            limit=_NO_CONCURRENCY,
        )

        list_of_fmds_to_delete = [
            expired_fmd
            for expired_fmd, updated_fmd in zip(
                list_of_expired_uploads, updated_fmds, strict=True
            )
            if not isinstance(updated_fmd, FileMetaDataAtDB)
        ]

        # try to revert the files if they exist
        async def _revert_file(fmd: FileMetaDataAtDB) -> FileMetaDataAtDB:
            if is_valid_managed_multipart_upload(fmd.upload_id):
                assert fmd.upload_id  # nosec
                await s3_client.abort_multipart_upload(
                    bucket=fmd.bucket_name,
                    object_key=fmd.file_id,
                    upload_id=fmd.upload_id,
                )
            await s3_client.undelete_object(
                bucket=fmd.bucket_name, object_key=fmd.file_id
            )
            return await self._update_database_from_storage(fmd)

        s3_client = get_s3_client(self.app)
        # NOTE: no concurrency here as we want to run low resources
        reverted_fmds = await limited_gather(
            *(_revert_file(fmd) for fmd in list_of_fmds_to_delete),
            reraise=False,
            log=_logger,
            limit=_NO_CONCURRENCY,
        )
        list_of_fmds_to_delete = [
            fmd
            for fmd, reverted_fmd in zip(
                list_of_fmds_to_delete, reverted_fmds, strict=True
            )
            if not isinstance(reverted_fmd, FileMetaDataAtDB)
        ]

        if list_of_fmds_to_delete:
            # delete the remaining ones
            _logger.debug(
                "following unfinished/incomplete uploads will now be deleted : [%s]",
                [fmd.file_id for fmd in list_of_fmds_to_delete],
            )
            for fmd in list_of_fmds_to_delete:
                if fmd.user_id is not None:
                    await self.delete_file(fmd.user_id, fmd.file_id)

            _logger.warning(
                "pending/incomplete uploads of [%s] removed",
                [fmd.file_id for fmd in list_of_fmds_to_delete],
            )

    async def clean_expired_uploads(self) -> None:
        await self._clean_expired_uploads()

    async def _update_fmd_from_other(
        self,
        *,
        fmd: FileMetaDataAtDB,
        copy_from: FileMetaDataAtDB,
    ) -> FileMetaDataAtDB:
        if not fmd.is_directory:
            s3_metadata = await get_s3_client(self.app).get_object_metadata(
                bucket=fmd.bucket_name, object_key=fmd.object_name
            )
            fmd.file_size = TypeAdapter(ByteSize).validate_python(s3_metadata.size)
            fmd.last_modified = s3_metadata.last_modified
            fmd.entity_tag = s3_metadata.e_tag
        else:
            # we spare calling get_directory_metadata as it is not needed now and is costly
            fmd.file_size = copy_from.file_size

        fmd.upload_expires_at = None
        fmd.upload_id = None

        return await FileMetaDataRepository.instance(get_db_engine(self.app)).upsert(
            fmd=convert_db_to_model(fmd)
        )

    async def _get_s3_metadata(
        self, fmd: FileMetaDataAtDB
    ) -> S3MetaData | S3DirectoryMetaData:
        return (
            await get_s3_client(self.app).get_object_metadata(
                bucket=fmd.bucket_name, object_key=fmd.object_name
            )
            if not fmd.is_directory
            else await get_s3_client(self.app).get_directory_metadata(
                bucket=fmd.bucket_name, prefix=fmd.object_name
            )
        )

    async def _update_database_from_storage(
        self, fmd: FileMetaDataAtDB
    ) -> FileMetaDataAtDB:
        """
        Raises:
            S3KeyNotFoundError -- if the object key is not found in S3
        """
        s3_metadata = await self._get_s3_metadata(fmd)
        if not fmd.is_directory:
            assert isinstance(s3_metadata, S3MetaData)  # nosec
            fmd.file_size = TypeAdapter(ByteSize).validate_python(s3_metadata.size)
            fmd.last_modified = s3_metadata.last_modified
            fmd.entity_tag = s3_metadata.e_tag
        elif fmd.is_directory:
            assert isinstance(s3_metadata, S3DirectoryMetaData)  # nosec
            fmd.file_size = TypeAdapter(ByteSize).validate_python(s3_metadata.size)
        fmd.upload_expires_at = None
        fmd.upload_id = None

        return await FileMetaDataRepository.instance(get_db_engine(self.app)).upsert(
            fmd=convert_db_to_model(fmd)
        )

    async def _copy_file_datcore_s3(
        self,
        user_id: UserID,
        source_uuid: str,
        dest_project_id: ProjectID,
        dest_node_id: NodeID,
        file_storage_link: dict[str, Any],
        bytes_transfered_cb: UploadedBytesTransferredCallback,
    ) -> FileMetaData:
        session = get_client_session(self.app)
        # 2 steps: Get download link for local copy, then upload to S3
        api_token, api_secret = await TokenRepository.instance(
            get_db_engine(self.app)
        ).get_api_token_and_secret(user_id=user_id)
        assert api_token  # nosec
        assert api_secret  # nosec
        dc_link = await datcore_adapter.get_file_download_presigned_link(
            self.app, api_token, api_secret, source_uuid
        )
        assert dc_link.path  # nosec
        filename = Path(dc_link.path).name
        dst_file_id = TypeAdapter(SimcoreS3FileID).validate_python(
            f"{dest_project_id}/{dest_node_id}/{filename}"
        )
        _logger.debug("copying %s to %s", f"{source_uuid=}", f"{dst_file_id=}")

        with tempfile.TemporaryDirectory() as tmpdir:
            local_file_path = Path(tmpdir) / filename
            # Downloads DATCore -> local
            await download_to_file_or_raise(session, f"{dc_link}", local_file_path)

            # copying will happen using aioboto3, therefore multipart might happen
            new_fmd = await self._create_fmd_for_upload(
                user_id,
                dst_file_id,
                upload_id=S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID,
                is_directory=False,
                sha256_checksum=None,
            )
            # Uploads local -> S3
            await get_s3_client(self.app).upload_file(
                bucket=self.simcore_bucket_name,
                file=local_file_path,
                object_key=dst_file_id,
                bytes_transfered_cb=bytes_transfered_cb,
            )
            updated_fmd = await self._update_database_from_storage(fmd=new_fmd)
            file_storage_link["store"] = self.location_id
            file_storage_link["path"] = new_fmd.file_id

            _logger.info("copied %s to %s", f"{source_uuid=}", f"{updated_fmd=}")

        return convert_db_to_model(updated_fmd)

    async def _copy_path_s3_s3(
        self,
        user_id: UserID,
        *,
        src_fmd: FileMetaDataAtDB,
        dst_file_id: SimcoreS3FileID,
        bytes_transfered_cb: CopiedBytesTransferredCallback,
    ) -> FileMetaData:
        with log_context(
            _logger,
            logging.INFO,
            f"copying {src_fmd.file_id=} to {dst_file_id=}, {src_fmd.is_directory=}",
        ):
            # copying will happen using aioboto3, therefore multipart might happen
            # NOTE: connection must be released to ensure database update
            new_fmd = await self._create_fmd_for_upload(
                user_id,
                dst_file_id,
                upload_id=S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID,
                is_directory=src_fmd.is_directory,
                sha256_checksum=src_fmd.sha256_checksum,
            )

            s3_client = get_s3_client(self.app)

            if src_fmd.is_directory:
                await s3_client.copy_objects_recursively(
                    bucket=self.simcore_bucket_name,
                    src_prefix=src_fmd.object_name,
                    dst_prefix=new_fmd.object_name,
                    bytes_transfered_cb=bytes_transfered_cb,
                )
            else:
                await s3_client.copy_object(
                    bucket=self.simcore_bucket_name,
                    src_object_key=src_fmd.object_name,
                    dst_object_key=new_fmd.object_name,
                    bytes_transfered_cb=bytes_transfered_cb,
                )
            # we are done, let's update the copy with the src
            updated_fmd = await self._update_fmd_from_other(
                fmd=new_fmd, copy_from=src_fmd
            )
            return convert_db_to_model(updated_fmd)

    async def _create_fmd_for_upload(
        self,
        user_id: UserID,
        file_id: StorageFileID,
        upload_id: UploadID | None,
        *,
        is_directory: bool,
        sha256_checksum: SHA256Str | None,
    ) -> FileMetaDataAtDB:
        now = datetime.datetime.utcnow()
        upload_expiration_date = now + datetime.timedelta(
            seconds=get_application_settings(
                self.app
            ).STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS
        )
        fmd = FileMetaData.from_simcore_node(
            user_id=user_id,
            file_id=TypeAdapter(SimcoreS3FileID).validate_python(file_id),
            bucket=self.simcore_bucket_name,
            location_id=self.location_id,
            location_name=self.location_name,
            upload_expires_at=upload_expiration_date,
            upload_id=upload_id,
            is_directory=is_directory,
            sha256_checksum=sha256_checksum,
        )

        return await FileMetaDataRepository.instance(get_db_engine(self.app)).upsert(
            fmd=fmd
        )

    async def create_s3_export(
        self,
        user_id: UserID,
        object_keys: list[S3ObjectKey],
        *,
        progress_bar: ProgressBarData,
    ) -> StorageFileID:
        source_object_keys: set[tuple[UserSelectionStr, StorageFileID]] = set()

        # ensure all selected items have the same parent
        if not ensure_user_selection_from_same_base_directory(object_keys):
            raise SelectionNotAllowedError(selection=object_keys)

        # check access rights
        for object_key in object_keys:
            project_id = None
            with contextlib.suppress(ValueError):
                project_id = ProjectID(Path(object_key).parts[0])

            try:
                accessible_projects_ids = await get_accessible_project_ids(
                    get_db_engine(self.app), user_id=user_id, project_id=project_id
                )
            except ProjectAccessRightError as err:
                raise AccessRightError(
                    user_id=user_id,
                    file_id=object_key,
                    location_id=SimcoreS3DataManager.get_location_id(),
                ) from err
            if project_id is None or project_id not in accessible_projects_ids:
                raise AccessRightError(
                    user_id=user_id,
                    file_id=object_key,
                    location_id=SimcoreS3DataManager.get_location_id(),
                )

        for object_key in object_keys:
            async for meta_data_files in get_s3_client(self.app).list_objects_paginated(
                self.simcore_bucket_name, object_key
            ):
                for entry in meta_data_files:
                    source_object_keys.add((object_key, entry.object_key))

        _logger.debug(
            "User selection '%s' includes '%s' files",
            object_keys,
            len(source_object_keys),
        )

        try:
            destination_object_key = create_random_export_name(user_id)

            # The return type here isn't a `StorageFileID` object, but it includes a link.
            # Since most interfaces expect a `StorageFileID`, the actual object isn't used.
            # Avoiding the link also ensures we don't cross the service boundary,
            # keeping everything internal.
            await self.create_file_upload_links(
                user_id=user_id,
                file_id=destination_object_key,
                link_type=LinkType.S3,
                file_size_bytes=ByteSize(0),
                sha256_checksum=None,
                is_directory=False,
            )

            await create_and_upload_export(
                get_s3_client(self.app),
                ProjectRepository.instance(get_db_engine(self.app)),
                self.simcore_bucket_name,
                source_object_keys=source_object_keys,
                destination_object_keys=destination_object_key,
                progress_bar=progress_bar,
            )
        except Exception:  # pylint:disable=broad-exception-caught
            await self.abort_file_upload(
                user_id=user_id, file_id=destination_object_key
            )
            raise

        await self.complete_file_upload(
            file_id=destination_object_key, user_id=user_id, uploaded_parts=[]
        )

        _logger.debug("export available at '%s'", destination_object_key)

        return destination_object_key


def create_simcore_s3_data_manager(app: FastAPI) -> SimcoreS3DataManager:
    cfg = get_application_settings(app)
    assert cfg.STORAGE_S3  # nosec
    return SimcoreS3DataManager(
        simcore_bucket_name=TypeAdapter(S3BucketName).validate_python(
            cfg.STORAGE_S3.S3_BUCKET_NAME
        ),
        app=app,
    )
