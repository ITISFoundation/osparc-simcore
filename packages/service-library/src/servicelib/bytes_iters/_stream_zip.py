from collections.abc import AsyncIterable
from datetime import UTC, datetime
from stat import S_IFREG
from typing import TypeAlias

from models_library.bytes_iters import BytesIter, DataSize
from stream_zip import ZIP_32, AsyncMemberFile, async_stream_zip

from ..progress_bar import ProgressBarData
from ._models import BytesStreamer

FileNameInArchive: TypeAlias = str
ArchiveFileEntry: TypeAlias = tuple[FileNameInArchive, BytesStreamer]
ArchiveEntries: TypeAlias = list[ArchiveFileEntry]


async def _member_files_iter(
    archive_entries: ArchiveEntries, progress_bar: ProgressBarData
) -> AsyncIterable[AsyncMemberFile]:
    for file_name, byte_streamer in archive_entries:
        yield (
            file_name,
            datetime.now(UTC),
            S_IFREG | 0o600,
            ZIP_32,
            byte_streamer.with_progress_bytes_iter(progress_bar=progress_bar),
        )


async def get_zip_bytes_iter(
    archive_entries: ArchiveEntries,
    *,
    progress_bar: ProgressBarData | None = None,
    chunk_size: int,
) -> BytesIter:
    # NOTE: this is CPU bound task, even though the loop is not blocked,
    # the CPU is still used for compressing the content.
    if progress_bar is None:
        progress_bar = ProgressBarData(num_steps=1, description="zip archive stream")

    total_stream_lenth = DataSize(
        sum(bytes_streamer.data_size for _, bytes_streamer in archive_entries)
    )
    description = f"files: count={len(archive_entries)}, size={total_stream_lenth.human_readable()}"

    async with progress_bar.sub_progress(
        steps=total_stream_lenth, description=description, progress_unit="Byte"
    ) as sub_progress:
        # NOTE: do not disable compression or the streams will be
        # loaded fully in memory before yielding their content
        async for chunk in async_stream_zip(
            _member_files_iter(archive_entries, sub_progress), chunk_size=chunk_size
        ):
            yield chunk
