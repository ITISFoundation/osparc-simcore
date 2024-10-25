import logging
from asyncio import CancelledError
from dataclasses import dataclass
from pathlib import Path

import aiofiles
from aiohttp import ClientSession
from models_library.api_schemas_storage import (
    ETag,
    FileMetaDataGet,
    FileUploadSchema,
    LinkType,
    UploadedPart,
)
from models_library.basic_types import IDStr, SHA256Str
from models_library.projects_nodes_io import LocationID, LocationName, StorageFileID
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize, TypeAdapter
from servicelib.file_utils import create_sha256_checksum
from servicelib.progress_bar import ProgressBarData
from settings_library.aws_s3_cli import AwsS3CliSettings
from settings_library.node_ports import NodePortsSettings
from settings_library.r_clone import RCloneSettings
from tenacity import AsyncRetrying
from tenacity.after import after_log
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_random_exponential
from yarl import URL

from ..node_ports_common.client_session_manager import ClientSessionContextManager
from . import aws_s3_cli, exceptions, r_clone, storage_client
from ._filemanager import _abort_upload, _complete_upload, _resolve_location_id
from .file_io_utils import (
    LogRedirectCB,
    UploadableFileObject,
    download_link_to_file,
    upload_file_to_presigned_links,
)

_logger = logging.getLogger(__name__)


async def complete_file_upload(
    uploaded_parts: list[UploadedPart],
    upload_completion_link: AnyUrl,
    client_session: ClientSession | None = None,
) -> ETag:
    async with ClientSessionContextManager(client_session) as session:
        e_tag: ETag | None = await _complete_upload(
            session=session,
            upload_completion_link=upload_completion_link,
            parts=uploaded_parts,
            is_directory=False,
        )
    # should not be None because a file is being uploaded
    assert e_tag is not None  # nosec
    return e_tag


async def get_download_link_from_s3(
    *,
    user_id: UserID,
    store_name: LocationName | None,
    store_id: LocationID | None,
    s3_object: StorageFileID,
    link_type: LinkType,
    client_session: ClientSession | None = None,
) -> URL:
    """
    :raises exceptions.NodeportsException
    :raises exceptions.S3InvalidPathError
    :raises exceptions.StorageInvalidCall
    :raises exceptions.StorageServerIssue
    """
    async with ClientSessionContextManager(client_session) as session:
        store_id = await _resolve_location_id(session, user_id, store_name, store_id)
        file_link = await storage_client.get_download_file_link(
            session=session,
            file_id=s3_object,
            location_id=store_id,
            user_id=user_id,
            link_type=link_type,
        )
        return URL(f"{file_link}")


async def get_upload_links_from_s3(
    *,
    user_id: UserID,
    store_name: LocationName | None,
    store_id: LocationID | None,
    s3_object: StorageFileID,
    link_type: LinkType,
    client_session: ClientSession | None = None,
    file_size: ByteSize,
    is_directory: bool,
    sha256_checksum: SHA256Str | None,
) -> tuple[LocationID, FileUploadSchema]:
    async with ClientSessionContextManager(client_session) as session:
        store_id = await _resolve_location_id(session, user_id, store_name, store_id)
        file_links = await storage_client.get_upload_file_links(
            session=session,
            file_id=s3_object,
            location_id=store_id,
            user_id=user_id,
            link_type=link_type,
            file_size=file_size,
            is_directory=is_directory,
            sha256_checksum=sha256_checksum,
        )
        return (store_id, file_links)


async def download_path_from_s3(
    *,
    user_id: UserID,
    store_name: LocationName | None,
    store_id: LocationID | None,
    s3_object: StorageFileID,
    local_path: Path,
    io_log_redirect_cb: LogRedirectCB | None,
    client_session: ClientSession | None = None,
    r_clone_settings: RCloneSettings | None,
    progress_bar: ProgressBarData,
    aws_s3_cli_settings: AwsS3CliSettings | None,
) -> Path:
    """Downloads a file from S3

    :param session: add app[APP_CLIENT_SESSION_KEY] session here otherwise default is opened/closed every call
    :type session: ClientSession, optional
    :raises exceptions.NodeportsException
    :raises exceptions.S3InvalidPathError
    :raises exceptions.StorageInvalidCall
    :return: path to downloaded file
    """
    _logger.debug(
        "Downloading from store %s:id %s, s3 object %s, to %s",
        store_name,
        store_id,
        s3_object,
        local_path,
    )

    async with ClientSessionContextManager(client_session) as session:
        store_id = await _resolve_location_id(session, user_id, store_name, store_id)
        file_meta_data: FileMetaDataGet = await _get_file_meta_data(
            user_id=user_id,
            s3_object=s3_object,
            store_id=store_id,
            client_session=session,
        )

        if (
            file_meta_data.is_directory
            and not aws_s3_cli_settings
            and not await r_clone.is_r_clone_available(r_clone_settings)
        ):
            msg = f"Requested to download directory {s3_object}, but no rclone support was detected"
            raise exceptions.NodeportsException(msg)
        if (
            file_meta_data.is_directory
            and aws_s3_cli_settings
            and not await aws_s3_cli.is_aws_s3_cli_available(aws_s3_cli_settings)
        ):
            msg = f"Requested to download directory {s3_object}, but no aws cli support was detected"
            raise exceptions.NodeportsException(msg)

        # get the s3 link
        download_link = await get_download_link_from_s3(
            user_id=user_id,
            store_name=store_name,
            store_id=store_id,
            s3_object=s3_object,
            client_session=session,
            link_type=(
                LinkType.S3 if file_meta_data.is_directory else LinkType.PRESIGNED
            ),
        )

        # the link contains the file name
        if not download_link:
            raise exceptions.S3InvalidPathError(s3_object)

        if file_meta_data.is_directory:
            if aws_s3_cli_settings:
                await aws_s3_cli.sync_s3_to_local(
                    aws_s3_cli_settings,
                    progress_bar,
                    local_directory_path=local_path,
                    download_s3_link=TypeAdapter(AnyUrl).validate_python(
                        f"{download_link}"
                    ),
                )
            elif r_clone_settings:
                await r_clone.sync_s3_to_local(
                    r_clone_settings,
                    progress_bar,
                    local_directory_path=local_path,
                    download_s3_link=str(
                        TypeAdapter(AnyUrl).validate_python(f"{download_link}")
                    ),
                )
            else:
                msg = "Unexpected configuration"
                raise RuntimeError(msg)
            return local_path

        return await download_file_from_link(
            download_link,
            local_path,
            client_session=session,
            io_log_redirect_cb=io_log_redirect_cb,
            progress_bar=progress_bar,
        )


async def download_file_from_link(
    download_link: URL,
    destination_folder: Path,
    *,
    io_log_redirect_cb: LogRedirectCB | None,
    file_name: str | None = None,
    client_session: ClientSession | None = None,
    progress_bar: ProgressBarData,
) -> Path:
    # a download link looks something like:
    # http://172.16.9.89:9001/simcore-test/269dec55-6d18-4901-a767-b567db23d425/4ccf4e2e-a6cd-4f77-a255-4c36fa1b1c72/test.test?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=s3access/20190719/us-east-1/s3/aws4_request&X-Amz-Date=20190719T142431Z&X-Amz-Expires=259200&X-Amz-SignedHeaders=host&X-Amz-Signature=90268f3b580b38c1aad128475936c6f5fd335d11d01ec143cca1056d92a724b5
    local_file_path = destination_folder / (file_name or Path(download_link.path).name)

    # remove an already existing file if present
    if local_file_path.exists():
        local_file_path.unlink()

    if io_log_redirect_cb:
        await io_log_redirect_cb(f"downloading {local_file_path}, please wait...")
    async with ClientSessionContextManager(client_session) as session:
        await download_link_to_file(
            session,
            download_link,
            local_file_path,
            num_retries=NodePortsSettings.create_from_envs().NODE_PORTS_IO_NUM_RETRY_ATTEMPTS,
            io_log_redirect_cb=io_log_redirect_cb,
            progress_bar=progress_bar,
        )
    if io_log_redirect_cb:
        await io_log_redirect_cb(f"download of {local_file_path} complete.")
    return local_file_path


async def abort_upload(
    abort_upload_link: AnyUrl, client_session: ClientSession | None = None
) -> None:
    """Abort a multipart upload

    Arguments:
        upload_links: FileUploadSchema

    """
    async with ClientSessionContextManager(client_session) as session:
        await _abort_upload(
            session=session,
            abort_upload_link=abort_upload_link,
            reraise_exceptions=True,
        )


@dataclass
class UploadedFile:
    store_id: LocationID
    etag: ETag


@dataclass
class UploadedFolder:
    ...


async def _generate_checksum(
    path_to_upload: Path | UploadableFileObject, is_directory: bool
) -> SHA256Str | None:
    checksum: SHA256Str | None = None
    if is_directory:
        return checksum
    if isinstance(path_to_upload, Path):
        async with aiofiles.open(path_to_upload, mode="rb") as f:
            checksum = SHA256Str(await create_sha256_checksum(f))
    elif isinstance(path_to_upload, UploadableFileObject):
        checksum = path_to_upload.sha256_checksum
    return checksum


async def upload_path(  # pylint: disable=too-many-arguments
    *,
    user_id: UserID,
    store_id: LocationID | None,
    store_name: LocationName | None,
    s3_object: StorageFileID,
    path_to_upload: Path | UploadableFileObject,
    io_log_redirect_cb: LogRedirectCB | None,
    client_session: ClientSession | None = None,
    r_clone_settings: RCloneSettings | None = None,
    progress_bar: ProgressBarData | None = None,
    exclude_patterns: set[str] | None = None,
    aws_s3_cli_settings: AwsS3CliSettings | None = None,
) -> UploadedFile | UploadedFolder:
    """Uploads a file (potentially in parallel) or a file object (sequential in any case) to S3

    :param session: add app[APP_CLIENT_SESSION_KEY] session here otherwise default is opened/closed every call
    :type session: ClientSession, optional
    :raises exceptions.S3InvalidPathError
    :raises exceptions.S3TransferError
    :raises exceptions.NodeportsException
    :return: stored id, S3 entity_tag
    """
    async for attempt in AsyncRetrying(
        reraise=True,
        wait=wait_random_exponential(),
        stop=stop_after_attempt(
            NodePortsSettings.create_from_envs().NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS
        ),
        retry=retry_if_exception_type(exceptions.AwsS3BadRequestRequestTimeoutError),
        before_sleep=before_sleep_log(_logger, logging.WARNING, exc_info=True),
        after=after_log(_logger, log_level=logging.ERROR),
    ):
        with attempt:
            result = await _upload_path(
                user_id=user_id,
                store_id=store_id,
                store_name=store_name,
                s3_object=s3_object,
                path_to_upload=path_to_upload,
                io_log_redirect_cb=io_log_redirect_cb,
                client_session=client_session,
                r_clone_settings=r_clone_settings,
                progress_bar=progress_bar,
                exclude_patterns=exclude_patterns,
                aws_s3_cli_settings=aws_s3_cli_settings,
            )
    return result


async def _upload_path(  # pylint: disable=too-many-arguments
    *,
    user_id: UserID,
    store_id: LocationID | None,
    store_name: LocationName | None,
    s3_object: StorageFileID,
    path_to_upload: Path | UploadableFileObject,
    io_log_redirect_cb: LogRedirectCB | None,
    client_session: ClientSession | None,
    r_clone_settings: RCloneSettings | None,
    progress_bar: ProgressBarData | None,
    exclude_patterns: set[str] | None,
    aws_s3_cli_settings: AwsS3CliSettings | None,
) -> UploadedFile | UploadedFolder:
    _logger.debug(
        "Uploading %s to %s:%s@%s",
        f"{path_to_upload=}",
        f"{store_id=}",
        f"{store_name=}",
        f"{s3_object=}",
    )

    if not progress_bar:
        progress_bar = ProgressBarData(num_steps=1, description=IDStr("uploading"))

    is_directory: bool = isinstance(path_to_upload, Path) and path_to_upload.is_dir()
    if (
        is_directory
        and not aws_s3_cli_settings
        and not await r_clone.is_r_clone_available(r_clone_settings)
    ):
        msg = f"Requested to upload directory {path_to_upload}, but no rclone support was detected"
        raise exceptions.NodeportsException(msg)
    if (
        is_directory
        and aws_s3_cli_settings
        and not await aws_s3_cli.is_aws_s3_cli_available(aws_s3_cli_settings)
    ):
        msg = f"Requested to upload directory {path_to_upload}, but no aws cli support was detected"
        raise exceptions.NodeportsException(msg)

    checksum: SHA256Str | None = await _generate_checksum(path_to_upload, is_directory)
    if io_log_redirect_cb:
        await io_log_redirect_cb(f"uploading {path_to_upload}, please wait...")

    # NOTE: when uploading a directory there is no e_tag as this is provided only for
    # each single file and it makes no sense to have one for directories
    e_tag: ETag | None = None
    async with ClientSessionContextManager(client_session) as session:
        upload_links: FileUploadSchema | None = None
        try:
            store_id, upload_links = await get_upload_links_from_s3(
                user_id=user_id,
                store_name=store_name,
                store_id=store_id,
                s3_object=s3_object,
                client_session=session,
                link_type=LinkType.S3 if is_directory else LinkType.PRESIGNED,
                file_size=ByteSize(
                    path_to_upload.stat().st_size
                    if isinstance(path_to_upload, Path)
                    else path_to_upload.file_size
                ),
                is_directory=is_directory,
                sha256_checksum=checksum,
            )
            e_tag, upload_links = await _upload_to_s3(
                upload_links=upload_links,
                path_to_upload=path_to_upload,
                io_log_redirect_cb=io_log_redirect_cb,
                r_clone_settings=r_clone_settings,
                progress_bar=progress_bar,
                is_directory=is_directory,
                session=session,
                exclude_patterns=exclude_patterns,
                aws_s3_cli_settings=aws_s3_cli_settings,
            )
        except (
            r_clone.RCloneFailedError,
            aws_s3_cli.AwsS3CliFailedError,
            exceptions.S3TransferError,
        ) as exc:
            _logger.exception("The upload failed with an unexpected error:")
            if upload_links:
                await _abort_upload(
                    session, upload_links.links.abort_upload, reraise_exceptions=False
                )
            raise exceptions.S3TransferError from exc
        except CancelledError:
            if upload_links:
                await _abort_upload(
                    session, upload_links.links.abort_upload, reraise_exceptions=False
                )
            raise
        if io_log_redirect_cb:
            await io_log_redirect_cb(f"upload of {path_to_upload} complete.")
    return UploadedFolder() if e_tag is None else UploadedFile(store_id, e_tag)


async def _upload_to_s3(
    *,
    upload_links,
    path_to_upload: Path | UploadableFileObject,
    io_log_redirect_cb: LogRedirectCB | None,
    r_clone_settings: RCloneSettings | None,
    progress_bar: ProgressBarData,
    is_directory: bool,
    session: ClientSession,
    exclude_patterns: set[str] | None,
    aws_s3_cli_settings: AwsS3CliSettings | None,
) -> tuple[ETag | None, FileUploadSchema]:
    uploaded_parts: list[UploadedPart] = []
    if is_directory:
        assert isinstance(path_to_upload, Path)  # nosec
        assert len(upload_links.urls) > 0  # nosec
        if aws_s3_cli_settings:
            await aws_s3_cli.sync_local_to_s3(
                aws_s3_cli_settings,
                progress_bar,
                local_directory_path=path_to_upload,
                upload_s3_link=upload_links.urls[0],
                exclude_patterns=exclude_patterns,
            )
        elif r_clone_settings:
            await r_clone.sync_local_to_s3(
                r_clone_settings,
                progress_bar,
                local_directory_path=path_to_upload,
                upload_s3_link=upload_links.urls[0],
                exclude_patterns=exclude_patterns,
            )
        else:
            msg = "Unexpected configuration"
            raise RuntimeError(msg)
    else:
        uploaded_parts = await upload_file_to_presigned_links(
            session,
            upload_links,
            path_to_upload,
            num_retries=NodePortsSettings.create_from_envs().NODE_PORTS_IO_NUM_RETRY_ATTEMPTS,
            io_log_redirect_cb=io_log_redirect_cb,
            progress_bar=progress_bar,
        )
    # complete the upload
    e_tag = await _complete_upload(
        session,
        upload_links.links.complete_upload,
        uploaded_parts,
        is_directory=is_directory,
    )
    return e_tag, upload_links


async def _get_file_meta_data(
    user_id: UserID,
    store_id: LocationID,
    s3_object: StorageFileID,
    client_session: ClientSession | None = None,
) -> FileMetaDataGet:
    async with ClientSessionContextManager(client_session) as session:
        _logger.debug("Will request metadata for s3_object=%s", s3_object)

        file_metadata: FileMetaDataGet = await storage_client.get_file_metadata(
            session=session,
            file_id=s3_object,
            location_id=store_id,
            user_id=user_id,
        )
        _logger.debug(
            "Result for metadata s3_object=%s, result=%s",
            s3_object,
            f"{file_metadata=}",
        )
        return file_metadata


async def entry_exists(
    user_id: UserID,
    store_id: LocationID,
    s3_object: StorageFileID,
    client_session: ClientSession | None = None,
    *,
    is_directory: bool,
) -> bool:
    """
    Returns True if metadata for s3_object is present.
    Before returning it also checks if the metadata entry is a directory or a file.
    """
    try:
        file_metadata: FileMetaDataGet = await _get_file_meta_data(
            user_id, store_id, s3_object, client_session
        )
        result: bool = (
            file_metadata.file_id == s3_object
            and file_metadata.is_directory == is_directory
        )
        return result
    except exceptions.S3InvalidPathError as err:
        _logger.debug(
            "Failed request metadata for s3_object=%s with %s", s3_object, err
        )
        return False


@dataclass(kw_only=True, frozen=True, slots=True)
class FileMetaData:
    location: LocationID
    etag: ETag


async def get_file_metadata(
    user_id: UserID,
    store_id: LocationID,
    s3_object: StorageFileID,
    client_session: ClientSession | None = None,
) -> FileMetaData:
    """
    :raises S3InvalidPathError
    """
    file_metadata: FileMetaDataGet = await _get_file_meta_data(
        user_id=user_id,
        store_id=store_id,
        s3_object=s3_object,
        client_session=client_session,
    )
    assert file_metadata.location_id is not None  # nosec
    assert file_metadata.entity_tag is not None  # nosec
    return FileMetaData(
        location=file_metadata.location_id,
        etag=file_metadata.entity_tag,
    )


async def delete_file(
    user_id: UserID,
    store_id: LocationID,
    s3_object: StorageFileID,
    client_session: ClientSession | None = None,
) -> None:
    async with ClientSessionContextManager(client_session) as session:
        _logger.debug("Will delete file for s3_object=%s", s3_object)
        await storage_client.delete_file(
            session=session, file_id=s3_object, location_id=store_id, user_id=user_id
        )
