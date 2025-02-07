from collections.abc import AsyncIterable, Callable
from typing import TypeAlias

from pydantic import ByteSize

FileNameInArchive: TypeAlias = str
FileStream: TypeAlias = AsyncIterable[bytes]

FileStreamCallable: TypeAlias = Callable[[], FileStream]
FileSize: TypeAlias = ByteSize

StreamData: TypeAlias = tuple[FileSize, FileStreamCallable]

ArchiveFileEntry: TypeAlias = tuple[FileNameInArchive, StreamData]
ArchiveEntries: TypeAlias = list[ArchiveFileEntry]
