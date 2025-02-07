from typing import Final

from pydantic import ByteSize, TypeAdapter

DEFAULT_READ_CHUNK_SIZE: Final[int] = TypeAdapter(ByteSize).validate_python("1MiB")
MULTIPART_UPLOADS_MIN_TOTAL_SIZE: Final[ByteSize] = TypeAdapter(
    ByteSize
).validate_python("100MiB")
