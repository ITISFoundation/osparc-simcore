import logging
from pathlib import Path
from typing import Optional, Union

from aiohttp import ClientError, ClientSession
from models_library.api_schemas_storage import (
    ETag,
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadCompletionBody,
    FileUploadSchema,
    LocationID,
    LocationName,
    UploadedPart,
)
from models_library.generics import Envelope
from models_library.projects_nodes_io import StorageFileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import ByteSize, parse_obj_as
from settings_library.r_clone import RCloneSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

from ..node_ports_common.client_session_manager import ClientSessionContextManager
from . import exceptions, r_clone, storage_client
from .constants import SIMCORE_LOCATION
from .file_io_utils import (
    LogRedirectCB,
    UploadableFileObject,
    download_link_to_file,
    upload_file_to_presigned_links,
)
from .settings import NodePortsSettings

log = logging.getLogger(__name__)


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
    upload_links: FileUploadSchema,
    parts: list[UploadedPart],
) -> ETag:
    """completes a potentially multipart upload in AWS
    NOTE: it can take several minutes to finish, see [AWS documentation](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CompleteMultipartUpload.html)
    it can take several minutes
    :raises ValueError: _description_
    :raises exceptions.S3TransferError: _description_
    :rtype: ETag
    """
    async with session.post(
        upload_links.links.complete_upload,
        json=jsonable_encoder(FileUploadCompletionBody(parts=parts)),
    ) as resp:
        resp.raise_for_status()
        # now poll for state
        file_upload_complete_response = parse_obj_as(
            Envelope[FileUploadCompleteResponse], await resp.json()
        )
        assert file_upload_complete_response.data  # nosec
    state_url = file_upload_complete_response.data.links.state
    log.info(
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
        before_sleep=before_sleep_log(log, logging.DEBUG),
    ):
        with attempt:
            async with session.post(state_url) as resp:
                resp.raise_for_status()
                future_enveloped = parse_obj_as(
                    Envelope[FileUploadCompleteFutureResponse], await resp.json()
                )
                assert future_enveloped.data  # nosec
                if future_enveloped.data.state == FileUploadCompleteState.NOK:
                    raise ValueError("upload not ready yet")
            assert future_enveloped.data.e_tag  # nosec
            log.debug(
                "multipart upload completed in %s, received %s",
                attempt.retry_state.retry_object.statistics,
                f"{future_enveloped.data.e_tag=}",
            )
            return future_enveloped.data.e_tag
    raise exceptions.S3TransferError(
        f"Could not complete the upload of file {upload_links=}"
    )


async def get_download_link_from_s3(
    *,
    user_id: UserID,
    store_name: Optional[LocationName],
    store_id: Optional[LocationID],
    s3_object: StorageFileID,
    link_type: storage_client.LinkType,
    client_session: Optional[ClientSession] = None,
) -> URL:
    """
    :raises exceptions.NodeportsException
    :raises exceptions.S3InvalidPathError
    :raises exceptions.StorageInvalidCall
    :raises exceptions.StorageServerIssue
    """
    if store_name is None and store_id is None:
        raise exceptions.NodeportsException(msg="both store name and store id are None")

    async with ClientSessionContextManager(client_session) as session:
        if store_name is not None:
            store_id = await _get_location_id_from_location_name(
                user_id, store_name, session
            )
        assert store_id is not None  # nosec
        return URL(
            await storage_client.get_download_file_link(
                session=session,
                file_id=s3_object,
                location_id=store_id,
                user_id=user_id,
                link_type=link_type,
            )
        )


async def get_upload_links_from_s3(
    *,
    user_id: UserID,
    store_name: Optional[LocationName],
    store_id: Optional[LocationID],
    s3_object: StorageFileID,
    link_type: storage_client.LinkType,
    client_session: Optional[ClientSession] = None,
    file_size: ByteSize,
) -> tuple[LocationID, FileUploadSchema]:
    if store_name is None and store_id is None:
        raise exceptions.NodeportsException(msg="both store name and store id are None")

    async with ClientSessionContextManager(client_session) as session:
        if store_name is not None:
            store_id = await _get_location_id_from_location_name(
                user_id, store_name, session
            )
        assert store_id is not None  # nosec
        return (
            store_id,
            await storage_client.get_upload_file_links(
                session=session,
                file_id=s3_object,
                location_id=store_id,
                user_id=user_id,
                link_type=link_type,
                file_size=file_size,
            ),
        )


async def download_file_from_s3(
    *,
    user_id: UserID,
    store_name: Optional[LocationName],
    store_id: Optional[LocationID],
    s3_object: StorageFileID,
    local_folder: Path,
    io_log_redirect_cb: Optional[LogRedirectCB],
    client_session: Optional[ClientSession] = None,
) -> Path:
    """Downloads a file from S3

    :param session: add app[APP_CLIENT_SESSION_KEY] session here otherwise default is opened/closed every call
    :type session: ClientSession, optional
    :raises exceptions.S3InvalidPathError
    :raises exceptions.StorageInvalidCall
    :return: path to downloaded file
    """
    log.debug(
        "Downloading from store %s:id %s, s3 object %s, to %s",
        store_name,
        store_id,
        s3_object,
        local_folder,
    )

    async with ClientSessionContextManager(client_session) as session:
        # get the s3 link
        download_link = await get_download_link_from_s3(
            user_id=user_id,
            store_name=store_name,
            store_id=store_id,
            s3_object=s3_object,
            client_session=session,
            link_type=storage_client.LinkType.PRESIGNED,
        )

        # the link contains the file name
        if not download_link:
            raise exceptions.S3InvalidPathError(s3_object)

        return await download_file_from_link(
            download_link,
            local_folder,
            client_session=session,
            io_log_redirect_cb=io_log_redirect_cb,
        )


async def download_file_from_link(
    download_link: URL,
    destination_folder: Path,
    io_log_redirect_cb: Optional[LogRedirectCB],
    file_name: Optional[str] = None,
    client_session: Optional[ClientSession] = None,
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
        )
    if io_log_redirect_cb:
        await io_log_redirect_cb(f"download of {local_file_path} complete.")
    return local_file_path


async def _abort_upload(
    session: ClientSession, upload_links: FileUploadSchema, *, reraise_exceptions: bool
) -> None:
    try:
        async with session.post(upload_links.links.abort_upload) as resp:
            resp.raise_for_status()
    except ClientError:
        log.warning("Error while aborting upload", exc_info=True)
        if reraise_exceptions:
            raise


async def upload_file(
    *,
    user_id: UserID,
    store_id: Optional[LocationID],
    store_name: Optional[LocationName],
    s3_object: StorageFileID,
    file_to_upload: Union[Path, UploadableFileObject],
    io_log_redirect_cb: Optional[LogRedirectCB],
    client_session: Optional[ClientSession] = None,
    r_clone_settings: Optional[RCloneSettings] = None,
) -> tuple[LocationID, ETag]:
    """Uploads a file (potentially in parallel) or a file object (sequential in any case) to S3

    :param session: add app[APP_CLIENT_SESSION_KEY] session here otherwise default is opened/closed every call
    :type session: ClientSession, optional
    :raises exceptions.S3InvalidPathError
    :raises exceptions.S3TransferError
    :raises exceptions.NodeportsException
    :return: stored id, S3 entity_tag
    """
    log.debug(
        "Uploading %s to %s:%s@%s",
        f"{file_to_upload=}",
        f"{store_id=}",
        f"{store_name=}",
        f"{s3_object=}",
    )

    use_rclone = (
        await r_clone.is_r_clone_available(r_clone_settings)
        and store_id == SIMCORE_LOCATION
        and isinstance(file_to_upload, Path)
    )
    if io_log_redirect_cb:
        await io_log_redirect_cb(f"uploading {file_to_upload}, please wait...")
    async with ClientSessionContextManager(client_session) as session:
        upload_links = None
        try:
            store_id, upload_links = await get_upload_links_from_s3(
                user_id=user_id,
                store_name=store_name,
                store_id=store_id,
                s3_object=s3_object,
                client_session=session,
                link_type=storage_client.LinkType.S3
                if use_rclone
                else storage_client.LinkType.PRESIGNED,
                file_size=ByteSize(
                    file_to_upload.stat().st_size
                    if isinstance(file_to_upload, Path)
                    else file_to_upload.file_size
                ),
            )
            # NOTE: in case of S3 upload, there are no multipart uploads, so this remains empty
            uploaded_parts: list[UploadedPart] = []
            if use_rclone:
                assert r_clone_settings  # nosec
                assert isinstance(file_to_upload, Path)  # nosec
                await r_clone.sync_local_to_s3(
                    file_to_upload,
                    r_clone_settings,
                    upload_links,
                )
            else:
                uploaded_parts = await upload_file_to_presigned_links(
                    session,
                    upload_links,
                    file_to_upload,
                    num_retries=NodePortsSettings.create_from_envs().NODE_PORTS_IO_NUM_RETRY_ATTEMPTS,
                    io_log_redirect_cb=io_log_redirect_cb,
                )

            # complete the upload
            e_tag = await _complete_upload(
                session,
                upload_links,
                uploaded_parts,
            )
        except (r_clone.RCloneFailedError, exceptions.S3TransferError) as exc:
            log.error("The upload failed with an unexpected error:", exc_info=True)
            if upload_links:
                # abort the upload correctly, so it can revert back to last version
                await _abort_upload(session, upload_links, reraise_exceptions=False)
                log.warning("Upload aborted")
            raise exceptions.S3TransferError from exc
        if io_log_redirect_cb:
            await io_log_redirect_cb(f"upload of {file_to_upload} complete.")
        return store_id, e_tag


async def entry_exists(
    user_id: UserID,
    store_id: LocationID,
    s3_object: StorageFileID,
    client_session: Optional[ClientSession] = None,
) -> bool:
    """Returns True if metadata for s3_object is present"""
    try:
        async with ClientSessionContextManager(client_session) as session:
            log.debug("Will request metadata for s3_object=%s", s3_object)

            file_metadata: FileMetaDataGet = await storage_client.get_file_metadata(
                session=session,
                file_id=s3_object,
                location_id=store_id,
                user_id=user_id,
            )
            log.debug(
                "Result for metadata s3_object=%s, result=%s",
                s3_object,
                f"{file_metadata=}",
            )
            return bool(file_metadata.file_id == s3_object)
    except exceptions.S3InvalidPathError:
        return False


async def get_file_metadata(
    user_id: UserID,
    store_id: LocationID,
    s3_object: StorageFileID,
    client_session: Optional[ClientSession] = None,
) -> tuple[LocationID, ETag]:
    """
    :raises S3InvalidPathError
    """
    async with ClientSessionContextManager(client_session) as session:
        log.debug("Will request metadata for s3_object=%s", s3_object)
        file_metadata = await storage_client.get_file_metadata(
            session=session, file_id=s3_object, location_id=store_id, user_id=user_id
        )

    log.debug(
        "Result for metadata s3_object=%s, result=%s", s3_object, f"{file_metadata=}"
    )
    assert file_metadata.location_id is not None  # nosec
    assert file_metadata.entity_tag is not None  # nosec
    return (file_metadata.location_id, file_metadata.entity_tag)


async def delete_file(
    user_id: UserID,
    store_id: LocationID,
    s3_object: StorageFileID,
    client_session: Optional[ClientSession] = None,
) -> None:
    async with ClientSessionContextManager(client_session) as session:
        log.debug("Will delete file for s3_object=%s", s3_object)
        await storage_client.delete_file(
            session=session, file_id=s3_object, location_id=store_id, user_id=user_id
        )
