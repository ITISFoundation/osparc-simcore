import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import (
    IO,
    AsyncGenerator,
    Optional,
    Protocol,
    Union,
    cast,
    runtime_checkable,
)

import aiofiles
from aiohttp import (
    ClientConnectionError,
    ClientError,
    ClientPayloadError,
    ClientResponse,
    ClientResponseError,
    ClientSession,
    RequestInfo,
    web,
)
from aiohttp.typedefs import LooseHeaders
from models_library.api_schemas_storage import ETag, FileUploadSchema, UploadedPart
from pydantic import AnyUrl
from servicelib.utils import logged_gather
from tenacity._asyncio import AsyncRetrying
from tenacity.after import after_log
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception, retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential
from tqdm import tqdm
from tqdm.contrib.logging import tqdm_logging_redirect
from yarl import URL

from . import exceptions
from .constants import CHUNK_SIZE


@dataclass(frozen=True)
class UploadableFileObject:
    file_object: IO
    file_name: str
    file_size: int


class ExtendedClientResponseError(ClientResponseError):
    def __init__(
        self,
        request_info: RequestInfo,
        history: tuple[ClientResponse, ...],
        body: str,
        *,
        code: Optional[int] = None,
        status: Optional[int] = None,
        message: str = "",
        headers: Optional[LooseHeaders] = None,
    ):
        super().__init__(
            request_info,
            history,
            code=code,
            status=status,
            message=message,
            headers=headers,
        )
        self.body = body

    def __str__(self) -> str:
        # When dealing with errors coming from S3 it is hard to conclude
        # what is wrong from a generic `400 Bad Request` extending
        # stacktrace with body. SEE links below for details:
        # - https://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html
        # - https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingRESTError.html
        return (
            f"status={self.status}, "
            f"message={self.message}, "
            f"url={self.request_info.real_url}, "
            f"body={self.body}"
        )


async def _raise_for_status(response: ClientResponse) -> None:
    if response.status >= 400:
        body = await response.text()
        raise ExtendedClientResponseError(
            response.request_info,
            response.history,
            body,
            status=response.status,
            message=response.reason or "",
            headers=response.headers,
        )


def _compute_tqdm_miniters(byte_size: int) -> float:
    """ensures tqdm minimal iteration is 1.5 %"""
    return min(1.5 * byte_size / 100.0, 1.0)


async def _file_object_chunk_reader(
    file_object: IO, *, offset: int, total_bytes_to_read: int
) -> AsyncGenerator[bytes, None]:
    await asyncio.get_event_loop().run_in_executor(None, file_object.seek, offset)
    num_read_bytes = 0
    while chunk := await asyncio.get_event_loop().run_in_executor(
        None, file_object.read, min(CHUNK_SIZE, total_bytes_to_read - num_read_bytes)
    ):
        num_read_bytes += len(chunk)
        yield chunk


async def _file_chunk_reader(
    file: Path, *, offset: int, total_bytes_to_read: int
) -> AsyncGenerator[bytes, None]:
    async with aiofiles.open(file, "rb") as f:
        await f.seek(offset)
        num_read_bytes = 0
        while chunk := await f.read(
            min(CHUNK_SIZE, total_bytes_to_read - num_read_bytes)
        ):
            num_read_bytes += len(chunk)
            yield chunk


@dataclass(frozen=True)
class ProgressData:
    current: int
    total: int


@runtime_checkable
class LogRedirectCB(Protocol):
    async def __call__(
        self, msg: str, progress_data: Optional[ProgressData] = None
    ) -> None:
        ...


async def _file_chunk_writer(
    file: Path,
    response: ClientResponse,
    pbar: tqdm,
    io_log_redirect_cb: Optional[LogRedirectCB],
):
    async with aiofiles.open(file, "wb") as file_pointer:
        while chunk := await response.content.read(CHUNK_SIZE):
            await file_pointer.write(chunk)
            if io_log_redirect_cb and pbar.update(len(chunk)):
                await io_log_redirect_cb(f"{pbar}", ProgressData(pbar.n, pbar.total))


log = logging.getLogger(__name__)
_TQDM_FILE_OPTIONS = dict(
    unit="byte",
    unit_scale=True,
    unit_divisor=1024,
    colour="yellow",
    miniters=1,
)


async def download_link_to_file(
    session: ClientSession,
    url: URL,
    file_path: Path,
    *,
    num_retries: int,
    io_log_redirect_cb: Optional[LogRedirectCB],
):
    log.debug("Downloading from %s to %s", url, file_path)
    async for attempt in AsyncRetrying(
        reraise=True,
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(num_retries),
        retry=retry_if_exception_type(ClientConnectionError),
        before_sleep=before_sleep_log(log, logging.WARNING, exc_info=True),
        after=after_log(log, log_level=logging.ERROR),
    ):
        with attempt:
            async with session.get(url) as response:
                if response.status == 404:
                    raise exceptions.InvalidDownloadLinkError(url)
                if response.status > 299:
                    raise exceptions.TransferError(url)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                # SEE https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Length
                file_size = int(response.headers.get("Content-Length", 0)) or None
                try:
                    with tqdm_logging_redirect(
                        desc=f"downloading {url.path} --> {file_path.name}\n",
                        total=file_size,
                        **(
                            _TQDM_FILE_OPTIONS
                            | dict(
                                miniters=_compute_tqdm_miniters(file_size)
                                if file_size
                                else 1
                            )
                        ),
                    ) as pbar:
                        await _file_chunk_writer(
                            file_path, response, pbar, io_log_redirect_cb
                        )
                        log.debug("Download complete")
                except ClientPayloadError as exc:
                    raise exceptions.TransferError(url) from exc


def _check_for_aws_http_errors(exc: BaseException) -> bool:
    """returns: True if it should retry when http exception is detected"""

    if not isinstance(exc, ExtendedClientResponseError):
        return False

    client_error = cast(ExtendedClientResponseError, exc)

    # Sometimes AWS responds with a 500 or 503 which shall be retried,
    # form more information see:
    # https://aws.amazon.com/premiumsupport/knowledge-center/http-5xx-errors-s3/
    if client_error.status in (
        web.HTTPInternalServerError.status_code,
        web.HTTPServiceUnavailable.status_code,
    ):
        return True

    # Sometimes the request to S3 can time out and a 400 with a `RequestTimeout`
    # reason in the body will be received. This also needs retrying,
    # for more information see:
    # see https://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html
    if (
        client_error.status == web.HTTPBadRequest.status_code
        and "RequestTimeout" in client_error.body
    ):
        return True

    return False


async def _upload_file_part(
    session: ClientSession,
    file_to_upload: Union[Path, UploadableFileObject],
    part_index: int,
    file_offset: int,
    file_part_size: int,
    upload_url: AnyUrl,
    pbar: tqdm,
    num_retries: int,
    *,
    io_log_redirect_cb: Optional[LogRedirectCB],
) -> tuple[int, ETag]:
    file_uploader = _file_chunk_reader(
        file_to_upload,  # type: ignore
        offset=file_offset,
        total_bytes_to_read=file_part_size,
    )
    if isinstance(file_to_upload, UploadableFileObject):
        file_uploader = _file_object_chunk_reader(
            file_to_upload.file_object,
            offset=file_offset,
            total_bytes_to_read=file_part_size,
        )

    async for attempt in AsyncRetrying(
        reraise=True,
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(num_retries),
        retry=retry_if_exception_type(ClientConnectionError)
        | retry_if_exception(_check_for_aws_http_errors),
        before_sleep=before_sleep_log(log, logging.WARNING, exc_info=True),
        after=after_log(log, log_level=logging.ERROR),
    ):
        with attempt:
            async with session.put(
                upload_url,
                data=file_uploader,
                headers={
                    "Content-Length": f"{file_part_size}",
                },
            ) as response:
                await _raise_for_status(response)
                if io_log_redirect_cb and pbar.update(file_part_size):
                    await io_log_redirect_cb(
                        f"{pbar}", ProgressData(pbar.n, pbar.total)
                    )

                # NOTE: the response from minio does not contain a json body
                assert response.status == web.HTTPOk.status_code  # nosec
                assert response.headers  # nosec
                assert "Etag" in response.headers  # nosec
                received_e_tag = json.loads(response.headers["Etag"])
                return (part_index, received_e_tag)
    raise exceptions.S3TransferError(
        f"Unexpected error while transferring {file_to_upload} to {upload_url}"
    )


async def upload_file_to_presigned_links(
    session: ClientSession,
    file_upload_links: FileUploadSchema,
    file_to_upload: Union[Path, UploadableFileObject],
    *,
    num_retries: int,
    io_log_redirect_cb: Optional[LogRedirectCB],
) -> list[UploadedPart]:
    file_size = 0
    file_name = ""
    if isinstance(file_to_upload, Path):
        file_size = file_to_upload.stat().st_size
        file_name = file_to_upload.as_posix()
    else:
        file_size = file_to_upload.file_size
        file_name = file_to_upload.file_name

    file_chunk_size = int(file_upload_links.chunk_size)
    num_urls = len(file_upload_links.urls)
    last_chunk_size = file_size - file_chunk_size * (num_urls - 1)
    upload_tasks = []
    with tqdm_logging_redirect(
        desc=f"uploading {file_name}\n",
        total=file_size,
        **(_TQDM_FILE_OPTIONS | dict(miniters=_compute_tqdm_miniters(file_size))),
    ) as pbar:
        for index, upload_url in enumerate(file_upload_links.urls):
            this_file_chunk_size = (
                file_chunk_size if (index + 1) < num_urls else last_chunk_size
            )
            upload_tasks.append(
                _upload_file_part(
                    session,
                    file_to_upload,
                    index,
                    index * file_chunk_size,
                    this_file_chunk_size,
                    upload_url,
                    pbar,
                    num_retries,
                    io_log_redirect_cb=io_log_redirect_cb,
                )
            )
        try:
            results = await logged_gather(
                *upload_tasks,
                log=log,
                # NOTE: when the file object is already created it cannot be duplicated so
                # no concurrency is allowed in that case
                max_concurrency=4 if isinstance(file_to_upload, Path) else 1,
            )
            part_to_etag = [
                UploadedPart(number=index + 1, e_tag=e_tag) for index, e_tag in results
            ]
            return part_to_etag
        except ClientError as exc:
            raise exceptions.S3TransferError(
                f"Could not upload file {file_name} ({file_size=}, {file_chunk_size=}, {last_chunk_size=}):{exc}"
            ) from exc
