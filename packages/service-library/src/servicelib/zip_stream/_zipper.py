from collections.abc import AsyncIterable
from datetime import UTC, datetime
from stat import S_IFREG

from stream_zip import ZIP_32, AsyncMemberFile, async_stream_zip

from ..progress_bar import ProgressBarData
from ._constants import DEFAULT_READ_CHUNK_SIZE
from ._types import ArchiveEntries, FileStream


async def _member_files_iter(
    file_streams: ArchiveEntries, progress: ProgressBarData
) -> AsyncIterable[AsyncMemberFile]:
    for file_name, (stream_size, file_stream_handler) in file_streams:
        yield (
            file_name,
            datetime.now(UTC),
            S_IFREG | 0o600,
            ZIP_32,
            file_stream_handler(),
        )
        await progress.update(stream_size)


async def get_zip_archive_stream(
    archive_files: ArchiveEntries,
    *,
    progress_bar: ProgressBarData | None = None,
    chunk_size: int = DEFAULT_READ_CHUNK_SIZE
) -> FileStream:
    # NOTE: this is CPU bound task, even though the loop is not blocked,
    # the CPU is still used for compressing the content.
    if progress_bar is None:
        progress_bar = ProgressBarData(num_steps=1, description="zip archive stream")

    total_stream_lenth = sum(file_size for _, (file_size, _) in archive_files)

    async with progress_bar.sub_progress(
        steps=total_stream_lenth, description="streams_reader", progress_unit="Byte"
    ) as sub_progress:
        # NOTE: do not disable compression or the streams will be
        # loaded fully in memory before yielding their content
        async for chunk in async_stream_zip(
            _member_files_iter(archive_files, sub_progress), chunk_size=chunk_size
        ):
            yield chunk
