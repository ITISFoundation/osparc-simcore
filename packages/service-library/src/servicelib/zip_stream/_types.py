from collections.abc import AsyncIterable, Callable
from typing import TypeAlias

FileNameInArchive: TypeAlias = str
FileStream: TypeAlias = AsyncIterable[bytes]

ArchiveFileEntry: TypeAlias = tuple[FileNameInArchive, Callable[[], FileStream]]
ArchiveEntries: TypeAlias = list[ArchiveFileEntry]
