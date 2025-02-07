from typing import Final

from pydantic import ByteSize, TypeAdapter

# NOTE: AWS S3 upload limits https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html
MIN_MULTIPART_UPLOAD_CHUNK_SIZE: Final[int] = TypeAdapter(ByteSize).validate_python(
    "5MiB"
)
MULTIPART_COPY_THRESHOLD: Final[ByteSize] = TypeAdapter(ByteSize).validate_python(
    "100MiB"
)

PRESIGNED_LINK_MAX_SIZE: Final[ByteSize] = TypeAdapter(ByteSize).validate_python("5GiB")
S3_MAX_FILE_SIZE: Final[ByteSize] = TypeAdapter(ByteSize).validate_python("5TiB")
