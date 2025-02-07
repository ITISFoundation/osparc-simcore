from typing import Final

from pydantic import ByteSize, TypeAdapter

DEFAULT_CHUNK_SIZE: Final[int] = TypeAdapter(ByteSize).validate_python("1MiB")
