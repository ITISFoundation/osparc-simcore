from collections.abc import AsyncIterable
from datetime import UTC, datetime
from stat import S_IFREG

from stream_zip import ZIP_32, AsyncMemberFile, async_stream_zip

from ..progress_bar import ProgressBarData
from ._constants import MIN_MULTIPART_UPLOAD_CHUNK_SIZE
from ._models import ArchiveEntries, DataStream, FileSize


async def _member_files_iter(
    file_streams: ArchiveEntries, progress_bar: ProgressBarData
) -> AsyncIterable[AsyncMemberFile]:
    for file_name, stream_data in file_streams:
        yield (
            file_name,
            datetime.now(UTC),
            S_IFREG | 0o600,
            ZIP_32,
            stream_data.with_progress_data_stream(progress_bar=progress_bar),
        )


async def get_zip_archive_file_stream(
    archive_files: ArchiveEntries,
    *,
    progress_bar: ProgressBarData | None = None,
    chunk_size: int = MIN_MULTIPART_UPLOAD_CHUNK_SIZE,
) -> DataStream:
    # NOTE: this is CPU bound task, even though the loop is not blocked,
    # the CPU is still used for compressing the content.
    if progress_bar is None:
        progress_bar = ProgressBarData(num_steps=1, description="zip archive stream")

    total_stream_lenth = FileSize(
        sum(stream_data.file_size for _, stream_data in archive_files)
    )
    description = (
        f"STATS: count={len(archive_files)}, size={total_stream_lenth.human_readable()}"
    )

    async with progress_bar.sub_progress(
        steps=total_stream_lenth, description=description, progress_unit="Byte"
    ) as sub_progress:
        # NOTE: do not disable compression or the streams will be
        # loaded fully in memory before yielding their content
        async for chunk in async_stream_zip(
            _member_files_iter(archive_files, sub_progress), chunk_size=chunk_size
        ):
            yield chunk
