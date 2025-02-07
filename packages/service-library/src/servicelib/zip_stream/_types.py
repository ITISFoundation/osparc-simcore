from collections.abc import AsyncIterable, Callable
from typing import TypeAlias

from pydantic import ByteSize
from servicelib.progress_bar import ProgressBarData

FileNameInArchive: TypeAlias = str
FileStream: TypeAlias = AsyncIterable[bytes]

FileStreamCallable: TypeAlias = Callable[[ProgressBarData], FileStream]
FileSize: TypeAlias = ByteSize

StreamData: TypeAlias = tuple[FileSize, FileStreamCallable]

ArchiveFileEntry: TypeAlias = tuple[FileNameInArchive, StreamData]
ArchiveEntries: TypeAlias = list[ArchiveFileEntry]
