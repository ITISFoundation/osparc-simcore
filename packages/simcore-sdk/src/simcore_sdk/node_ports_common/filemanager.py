import logging
from asyncio import CancelledError
from dataclasses import dataclass
from pathlib import Path

from aiohttp import ClientError, ClientSession
from models_library.api_schemas_storage import (
    ETag,
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadCompletionBody,
    FileUploadSchema,
    LinkType,
    LocationID,
    LocationName,
    UploadedPart,
)
from models_library.generics import Envelope
from models_library.projects_nodes_io import StorageFileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, ByteSize, parse_obj_as
from servicelib.progress_bar import ProgressBarData
from settings_library.r_clone import RCloneSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

from ..node_ports_common.client_session_manager import ClientSessionContextManager
from . import exceptions, r_clone, storage_client
from .file_io_utils import (
    LogRedirectCB,
    UploadableFileObject,
    download_link_to_file,
    upload_file_to_presigned_links,
)
from .settings import NodePortsSettings

_logger = logging.getLogger(__name__)


async def _get_location_id_from_location_name(
    user_id: UserID,
    store: LocationName,
    session: ClientSession,
) -> LocationID:
    resp = await storage_client.get_storage_locations(session=session, user_id=user_id)
    for location in resp:
        if location.name == store:
            return location.id
    # location id not found
    raise exceptions.S3InvalidStore(store)


async def _complete_upload(
    session: ClientSession,
    upload_completion_link: AnyUrl,
    parts: list[UploadedPart],
    *,
    is_directory: bool,
) -> ETag | None:
    """completes a potentially multipart upload in AWS
    NOTE: it can take several minutes to finish, see [AWS documentation](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CompleteMultipartUpload.html)
    it can take several minutes
    :raises ValueError: _description_
    :raises exceptions.S3TransferError: _description_
    :rtype: ETag
    """
    async with session.post(
        upload_completion_link,
        json=jsonable_encoder(FileUploadCompletionBody(parts=parts)),
    ) as resp:
        resp.raise_for_status()
        # now poll for state
        file_upload_complete_response = parse_obj_as(
            Envelope[FileUploadCompleteResponse], await resp.json()
        )
        assert file_upload_complete_response.data  # nosec
    state_url = file_upload_complete_response.data.links.state
    _logger.info(
        "completed upload of %s",
        f"{len(parts)} parts, received {file_upload_complete_response.json(indent=2)}",
    )

    async for attempt in AsyncRetrying(
        reraise=True,
        wait=wait_fixed(1),
        stop=stop_after_delay(
            NodePortsSettings.create_from_envs().NODE_PORTS_MULTIPART_UPLOAD_COMPLETION_TIMEOUT_S
        ),
        retry=retry_if_exception_type(ValueError),
        before_sleep=before_sleep_log(_logger, logging.DEBUG),
    ):
        with attempt:
            async with session.post(state_url) as resp:
                resp.raise_for_status()
                future_enveloped = parse_obj_as(
                    Envelope[FileUploadCompleteFutureResponse], await resp.json()
                )
                assert future_enveloped.data  # nosec
                if future_enveloped.data.state == FileUploadCompleteState.NOK:
                    msg = "upload not ready yet"
                    raise ValueError(msg)
            if is_directory:
                assert future_enveloped.data.e_tag is None  # nosec
                return None

            assert future_enveloped.data.e_tag  # nosec
            _logger.debug(
                "multipart upload completed in %s, received %s",
                attempt.retry_state.retry_object.statistics,
                f"{future_enveloped.data.e_tag=}",
            )
            return future_enveloped.data.e_tag
    msg = f"Could not complete the upload using the upload_completion_link={upload_completion_link!r}"
    raise exceptions.S3TransferError(msg)


async def _resolve_location_id(
    client_session: ClientSession,
    user_id: UserID,
    store_name: LocationName | None,
    store_id: LocationID | None,
) -> LocationID:
    if store_name is None and store_id is None:
        msg = f"both {store_name=} and {store_id=} are None"
        raise exceptions.NodeportsException(msg)

    if store_name is not None:
        store_id = await _get_location_id_from_location_name(
            user_id, store_name, client_session
        )
    assert store_id is not None  # nosec
    return store_id


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
    assert (
        e_tag is not None
    )  # nosec - should be none because we are only uploading a file here
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

        if file_meta_data.is_directory and not await r_clone.is_r_clone_available(
            r_clone_settings
        ):
            msg = f"Requested to download directory {s3_object}, but no rclone support was detected"
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
            assert r_clone_settings  # nosec
            await r_clone.sync_s3_to_local(
                r_clone_settings,
                progress_bar,
                local_directory_path=local_path,
                download_s3_link=parse_obj_as(AnyUrl, f"{download_link}"),
            )
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


async def _abort_upload(
    session: ClientSession, upload_links: FileUploadSchema, *, reraise_exceptions: bool
) -> None:
    # abort the upload correctly, so it can revert back to last version
    try:
        async with session.post(upload_links.links.abort_upload) as resp:
            resp.raise_for_status()
    except ClientError:
        _logger.warning("Error while aborting upload", exc_info=True)
        if reraise_exceptions:
            raise
    _logger.warning("Upload aborted")


@dataclass
class UploadedFile:
    store_id: LocationID
    etag: ETag


@dataclass
class UploadedFolder:
    ...


async def upload_path(
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
) -> UploadedFile | UploadedFolder:
    """Uploads a file (potentially in parallel) or a file object (sequential in any case) to S3

    :param session: add app[APP_CLIENT_SESSION_KEY] session here otherwise default is opened/closed every call
    :type session: ClientSession, optional
    :raises exceptions.S3InvalidPathError
    :raises exceptions.S3TransferError
    :raises exceptions.NodeportsException
    :return: stored id, S3 entity_tag
    """
    _logger.debug(
        "Uploading %s to %s:%s@%s",
        f"{path_to_upload=}",
        f"{store_id=}",
        f"{store_name=}",
        f"{s3_object=}",
    )

    if not progress_bar:
        progress_bar = ProgressBarData(steps=1)

    is_directory: bool = isinstance(path_to_upload, Path) and path_to_upload.is_dir()
    if is_directory and not await r_clone.is_r_clone_available(r_clone_settings):
        msg = f"Requested to upload directory {path_to_upload}, but no rclone support was detected"
        raise exceptions.NodeportsException(msg)

    if io_log_redirect_cb:
        await io_log_redirect_cb(f"uploading {path_to_upload}, please wait...")

    # NOTE: when uploading a directory there is no e_tag as this is provided only for
    # each single file and it makes no sense to have one for directories
    e_tag: ETag | None = None
    async with ClientSessionContextManager(client_session) as session:
        upload_links = None
        try:
            store_id, e_tag, upload_links = await _upload_to_s3(
                user_id=user_id,
                store_id=store_id,
                store_name=store_name,
                s3_object=s3_object,
                path_to_upload=path_to_upload,
                io_log_redirect_cb=io_log_redirect_cb,
                r_clone_settings=r_clone_settings,
                progress_bar=progress_bar,
                is_directory=is_directory,
                session=session,
                exclude_patterns=exclude_patterns,
            )
        except (r_clone.RCloneFailedError, exceptions.S3TransferError) as exc:
            _logger.exception("The upload failed with an unexpected error:")
            if upload_links:
                await _abort_upload(session, upload_links, reraise_exceptions=False)
            raise exceptions.S3TransferError from exc
        except CancelledError:
            if upload_links:
                await _abort_upload(session, upload_links, reraise_exceptions=False)
            raise
        if io_log_redirect_cb:
            await io_log_redirect_cb(f"upload of {path_to_upload} complete.")
    return UploadedFolder() if e_tag is None else UploadedFile(store_id, e_tag)


async def _upload_to_s3(  # noqa: PLR0913
    *,
    user_id: UserID,
    store_id: LocationID | None,
    store_name: LocationName | None,
    s3_object: StorageFileID,
    path_to_upload: Path | UploadableFileObject,
    io_log_redirect_cb: LogRedirectCB | None,
    r_clone_settings: RCloneSettings | None,
    progress_bar: ProgressBarData,
    is_directory: bool,
    session: ClientSession,
    exclude_patterns: set[str] | None,
) -> tuple[LocationID, ETag | None, FileUploadSchema]:
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
    )

    uploaded_parts: list[UploadedPart] = []
    if is_directory:
        assert r_clone_settings  # nosec
        assert isinstance(path_to_upload, Path)  # nosec
        assert len(upload_links.urls) > 0  # nosec
        await r_clone.sync_local_to_s3(
            r_clone_settings,
            progress_bar,
            local_directory_path=path_to_upload,
            upload_s3_link=upload_links.urls[0],
            exclude_patterns=exclude_patterns,
        )
    else:
        # uploading a file
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
    return store_id, e_tag, upload_links


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


async def get_file_metadata(
    user_id: UserID,
    store_id: LocationID,
    s3_object: StorageFileID,
    client_session: ClientSession | None = None,
) -> tuple[LocationID, ETag]:
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
    return (file_metadata.location_id, file_metadata.entity_tag)


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
