from collections.abc import AsyncIterable
from datetime import UTC, datetime
from stat import S_IFREG

from stream_zip import ZIP_32, AsyncMemberFile, async_stream_zip

from ..progress_bar import ProgressBarData
from ._constants import DEFAULT_CHUNK_SIZE
from ._types import ArchiveEntries, FileStream


async def _iter_files(
    file_streams: ArchiveEntries, progress_bar: ProgressBarData
) -> AsyncIterable[AsyncMemberFile]:
    async with progress_bar.sub_progress(
        steps=len(file_streams), description="..."
    ) as sub_progress:
        for file_name, file_stream_handler in file_streams:
            yield (
                file_name,
                datetime.now(UTC),
                S_IFREG | 0o600,
                ZIP_32,
                file_stream_handler(),
            )
            await sub_progress.update(1)


async def get_zip_archive_stream(
    archive_files: ArchiveEntries, *, progress_bar: ProgressBarData | None = None
) -> FileStream:
    if progress_bar is None:
        progress_bar = ProgressBarData(num_steps=1, description="stream archiver")
    async for chunk in async_stream_zip(
        _iter_files(archive_files, progress_bar), chunk_size=DEFAULT_CHUNK_SIZE
    ):
        yield chunk
