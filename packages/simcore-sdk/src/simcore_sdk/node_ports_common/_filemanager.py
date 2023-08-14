import logging

from aiohttp import ClientError, ClientSession
from models_library.api_schemas_storage import (
    ETag,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadCompletionBody,
    LocationID,
    LocationName,
    UploadedPart,
)
from models_library.generics import Envelope
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, parse_obj_as
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from . import exceptions, storage_client
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


async def _abort_upload(
    session: ClientSession, abort_upload_link: AnyUrl, *, reraise_exceptions: bool
) -> None:
    # abort the upload correctly, so it can revert back to last version
    try:
        async with session.post(abort_upload_link) as resp:
            resp.raise_for_status()
    except ClientError:
        _logger.warning("Error while aborting upload", exc_info=True)
        if reraise_exceptions:
            raise
    _logger.warning("Upload aborted")
