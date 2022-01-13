import logging
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Union
from uuid import UUID

import aiofiles
import tenacity
from aiohttp import ClientSession
from aiohttp.typedefs import StrOrURL
from aiopg.sa.result import ResultProxy, RowProxy
from yarl import URL

from .models import FileMetaData, FileMetaDataEx

logger = logging.getLogger(__name__)


MAX_CHUNK_SIZE = 1024
RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30


@tenacity.retry(
    wait=tenacity.wait_fixed(RETRY_WAIT_SECS),
    stop=tenacity.stop_after_attempt(RETRY_COUNT),
    before_sleep=tenacity.before_sleep_log(logger, logging.INFO),
)
async def assert_enpoint_is_ok(
    session: ClientSession, url: URL, expected_response: int = 200
):
    """Tenace check to GET given url endpoint

    Typically used to check connectivity to a given service

    In sync code use as
        loop.run_until_complete( check_endpoint(url) )

    :param url: endpoint service URL
    :type url: URL
    :param expected_response: expected http status, defaults to 200 (OK)
    :param expected_response: int, optional
    """
    async with session.get(url) as resp:
        if resp.status != expected_response:
            raise AssertionError(f"{resp.status} != {expected_response}")


def is_url(location):
    return bool(URL(str(location)).host)


async def download_to_file_or_raise(
    session: ClientSession,
    url: StrOrURL,
    destination_path: Union[str, Path],
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
    async with session.get(url, raise_for_status=True) as response:
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(dest_file, mode="wb") as fh:
            async for chunk in response.content.iter_chunked(chunk_size):
                await fh.write(chunk)
                total_size += len(chunk)

    return total_size


def create_reverse_dns(*resource_name_parts) -> str:
    """
    Returns a name for the resource following the reverse domain name notation
    """
    # See https://en.wikipedia.org/wiki/Reverse_domain_name_notation
    return "io.simcore.storage" + ".".join(map(str, resource_name_parts))


@lru_cache()
def create_resource_uuid(*resource_name_parts) -> UUID:
    revers_dns = create_reverse_dns(*resource_name_parts)
    return uuid.uuid5(uuid.NAMESPACE_DNS, revers_dns)


def to_meta_data_extended(row: Union[ResultProxy, RowProxy]) -> FileMetaDataEx:
    assert row  # nosec
    meta = FileMetaData(**dict(row))  # type: ignore
    meta_extended = FileMetaDataEx(
        fmd=meta,
        parent_id=str(Path(meta.object_name).parent),
    )  # type: ignore
    return meta_extended


def is_file_entry_valid(file_metadata: FileMetaData) -> bool:
    return (
        file_metadata.entity_tag is not None
        and file_metadata.file_size is not None
        and file_metadata.file_size > 0
    )
