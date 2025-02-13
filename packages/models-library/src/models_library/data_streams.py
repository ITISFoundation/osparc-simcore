from collections.abc import AsyncIterable, Callable
from typing import TypeAlias

from pydantic import ByteSize

DataStream: TypeAlias = AsyncIterable[bytes]

DataStreamCallable: TypeAlias = Callable[[], DataStream]
DataSize: TypeAlias = ByteSize
