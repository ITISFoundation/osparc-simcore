import logging
import urllib.parse
from pathlib import Path

import aiofiles
from aiohttp import ClientSession
from aiohttp.typedefs import StrOrURL
from models_library.projects_nodes_io import StorageFileID
from models_library.users import UserID

from .constants import LOCATION_ID_TO_TAG_MAP, MAX_CHUNK_SIZE, UNDEFINED_LOCATION_TAG
from .models import FileMetaData

logger = logging.getLogger(__name__)


def get_location_from_id(location_id: int) -> str:
    try:
        return LOCATION_ID_TO_TAG_MAP[location_id]
    except (ValueError, KeyError):
        return UNDEFINED_LOCATION_TAG


async def download_to_file_or_raise(
    session: ClientSession,
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
    async with session.get(url, raise_for_status=True) as response:
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(dest_file, mode="wb") as fh:
            async for chunk in response.content.iter_chunked(chunk_size):
                await fh.write(chunk)
                total_size += len(chunk)

    return total_size


def is_file_entry_valid(file_metadata: FileMetaData) -> bool:
    return (
        file_metadata.entity_tag is not None
        and file_metadata.file_size > 0
        and file_metadata.upload_expires_at is None
    )


def create_upload_completion_task_name(user_id: UserID, file_id: StorageFileID) -> str:
    return f"upload_complete_task_{user_id}_{urllib.parse.quote(file_id, safe='')}"
