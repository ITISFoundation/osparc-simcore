from collections.abc import AsyncIterable
from datetime import UTC, datetime
from stat import S_IFREG

from stream_zip import ZIP_32, AsyncMemberFile, async_stream_zip

from ._types import ArchiveEntries, FileStream


async def _iter_member_files(
    file_streams: ArchiveEntries,
) -> AsyncIterable[AsyncMemberFile]:
    for file_name, file_stream_handler in file_streams:
        yield (
            file_name,
            datetime.now(UTC),
            S_IFREG | 0o600,
            ZIP_32,
            file_stream_handler(),
        )


async def get_zip_archive_stream(archive_files: ArchiveEntries) -> FileStream:
    async for chunk in async_stream_zip(_iter_member_files(archive_files)):
        yield chunk
