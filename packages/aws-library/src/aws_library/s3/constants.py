from typing import Final

from pydantic import ByteSize, parse_obj_as

# NOTE: AWS S3 upload limits https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html
MULTIPART_UPLOADS_MIN_TOTAL_SIZE: Final[ByteSize] = parse_obj_as(ByteSize, "100MiB")
MULTIPART_UPLOADS_MIN_PART_SIZE: Final[ByteSize] = parse_obj_as(ByteSize, "10MiB")


PRESIGNED_LINK_MAX_SIZE: Final[ByteSize] = parse_obj_as(ByteSize, "5GiB")
S3_MAX_FILE_SIZE: Final[ByteSize] = parse_obj_as(ByteSize, "5TiB")
