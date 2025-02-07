from typing import Final

from pydantic import ByteSize, TypeAdapter

DEFAULT_READ_CHUNK_SIZE: Final[int] = TypeAdapter(ByteSize).validate_python("1MiB")
MIN_MULTIPART_UPLOAD_CHUNK_SIZE: Final[int] = TypeAdapter(ByteSize).validate_python(
    "5MiB"
)
