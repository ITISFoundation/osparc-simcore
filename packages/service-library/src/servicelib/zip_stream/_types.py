from collections.abc import AsyncIterator, Callable
from typing import TypeAlias

FileNameInArchive: TypeAlias = str
FileStream: TypeAlias = AsyncIterator[bytes]

ArchiveFileEntry: TypeAlias = tuple[FileNameInArchive, Callable[[], FileStream]]
ArchiveEntries: TypeAlias = list[ArchiveFileEntry]
