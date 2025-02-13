from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass
from typing import TypeAlias

from pydantic import ByteSize
from servicelib.progress_bar import ProgressBarData

FileNameInArchive: TypeAlias = str
DataStream: TypeAlias = AsyncIterable[bytes]

DataStreamCallable: TypeAlias = Callable[[], DataStream]
FileSize: TypeAlias = ByteSize


@dataclass(frozen=True)
class StreamData:
    file_size: FileSize
    data_stream_callable: DataStreamCallable

    async def with_progress_data_stream(
        self, progress_bar: ProgressBarData
    ) -> DataStream:
        async for chunk in self.data_stream_callable():
            await progress_bar.update(len(chunk))
            yield chunk


ArchiveFileEntry: TypeAlias = tuple[FileNameInArchive, StreamData]
ArchiveEntries: TypeAlias = list[ArchiveFileEntry]
