from collections.abc import AsyncIterable, Callable
from typing import TypeAlias

from pydantic import ByteSize

type BytesIter = AsyncIterable[bytes]

type BytesIterCallable = Callable[[], BytesIter]
DataSize: TypeAlias = ByteSize
