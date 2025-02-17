from collections.abc import AsyncIterable, Callable
from typing import TypeAlias

from pydantic import ByteSize

BytesIter: TypeAlias = AsyncIterable[bytes]

BytesIterCallable: TypeAlias = Callable[[], BytesIter]
DataSize: TypeAlias = ByteSize
