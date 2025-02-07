from collections.abc import AsyncIterator, Callable, Iterable
from typing import TypeAlias

FileNameInArchive: TypeAlias = str
FileStream: TypeAlias = AsyncIterator[bytes]

ArchiveFileEntry: TypeAlias = tuple[FileNameInArchive, Callable[[], FileStream]]
ArchiveEntries: TypeAlias = Iterable[ArchiveFileEntry]
