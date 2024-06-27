from .client import SimcoreS3API
from .constants import PRESIGNED_LINK_MAX_SIZE, S3_MAX_FILE_SIZE
from .errors import (
    S3AccessError,
    S3BucketInvalidError,
    S3DestinationNotEmptyError,
    S3KeyNotFoundError,
    S3NotConnectedError,
    S3RuntimeError,
    S3UploadNotFoundError,
)
from .models import (
    MultiPartUploadLinks,
    S3DirectoryMetaData,
    S3MetaData,
    S3ObjectKey,
    UploadID,
)

__all__: tuple[str, ...] = (
    "SimcoreS3API",
    "PRESIGNED_LINK_MAX_SIZE",
    "S3_MAX_FILE_SIZE",
    "S3AccessError",
    "S3BucketInvalidError",
    "S3DestinationNotEmptyError",
    "S3KeyNotFoundError",
    "S3NotConnectedError",
    "S3RuntimeError",
    "S3UploadNotFoundError",
    "S3DirectoryMetaData",
    "S3MetaData",
    "S3ObjectKey",
    "MultiPartUploadLinks",
    "UploadID",
)

# nopycln: file
