import datetime
import logging
from pathlib import Path
from typing import Annotated

import aiofiles
import httpx
from aiohttp.typedefs import StrOrURL
from annotated_types import doc
from aws_library.s3 import UploadID

from ..constants import MAX_CHUNK_SIZE, S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID
from ..models import FileMetaData, FileMetaDataAtDB

logger = logging.getLogger(__name__)


def convert_db_to_model(x: FileMetaDataAtDB) -> FileMetaData:
    model: FileMetaData = FileMetaData.model_validate(
        x.model_dump()
        | {
            "file_uuid": x.file_id,
            "file_name": x.file_id.split("/")[-1],
        }
    )
    return model


async def download_to_file_or_raise(
    client: httpx.AsyncClient,
    url: StrOrURL,
    destination_path: Path,
    *,
    chunk_size=MAX_CHUNK_SIZE,
) -> int:
    """
    Downloads content from url into destination_path

    Returns downloaded file size

    May raise aiohttp.ClientErrors:
     - aiohttp.ClientResponseError if not 2XX
     - aiohttp.ClientPayloadError while streaming chunks
    """
    # SEE Streaming API: https://docs.aiohttp.org/en/stable/streams.html

    dest_file = Path(destination_path)

    total_size = 0
    response = await client.get(f"{url}")
    response.raise_for_status()
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(dest_file, mode="wb") as fh:
        async for chunk in response.aiter_bytes(chunk_size):
            await fh.write(chunk)
            total_size += len(chunk)

    return total_size


def is_file_entry_valid(file_metadata: FileMetaData | FileMetaDataAtDB) -> bool:
    """checks if the file_metadata is valid"""
    return (
        file_metadata.entity_tag is not None
        and file_metadata.file_size > 0
        and file_metadata.upload_id is None
        and file_metadata.upload_expires_at is None
    )


def _to_utc(value: datetime.datetime) -> datetime.datetime:
    """Timestamps stored without a time zone in this table are UTC instants."""
    return value.astimezone(datetime.UTC) if value.tzinfo is not None else value.replace(tzinfo=datetime.UTC)


def is_upload_in_progress(
    file_metadata: FileMetaData | FileMetaDataAtDB,
    *,
    now: Annotated[
        datetime.datetime | None,
        doc("reference instant, defaults to the current time; naive values are read as UTC"),
    ] = None,
) -> bool:
    """True while upload links handed out for this entry have not expired.

    upload_expires_at is set when the links are handed out and cleared once the entry is
    resynchronized, so it marks the window in which an upload is expected to land. It is
    armed for single and multipart uploads alike: only multipart uploads also get an
    upload_id, so that column cannot be used to tell the window apart.
    The object is removed from S3 before the links are created, hence a missing object is
    expected while this is true and must not be reported as lost data.
    """
    if file_metadata.upload_expires_at is None:
        return False
    reference_time = datetime.datetime.now(tz=datetime.UTC) if now is None else _to_utc(now)
    return _to_utc(file_metadata.upload_expires_at) > reference_time


def is_valid_managed_multipart_upload(upload_id: UploadID | None) -> bool:
    """the upload ID is valid (created by storage service) AND internally managed
    by storage (e.g. PRESIGNED multipart upload)

    :type upload_id: Optional[UploadID]
    :rtype: bool
    """
    return upload_id is not None and upload_id != S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID
