from typing import Final

from aws_library.s3 import PRESIGNED_LINK_MAX_SIZE, S3_MAX_FILE_SIZE
from models_library.api_schemas_storage import LinkType
from pydantic import ByteSize

RETRY_WAIT_SECS = 2
MAX_CHUNK_SIZE = 1024
MINUTE = 60

UPLOAD_TASKS_KEY = f"{__name__}.upload_tasks"

# DSM locations
SIMCORE_S3_ID = 0
SIMCORE_S3_STR = "simcore.s3"

DATCORE_ID = 1
DATCORE_STR = "datcore"

# NOTE: SAFE S3 characters are found here [https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-keys.html]
# the % character was added since we need to url encode some of them
_SAFE_S3_FILE_NAME_RE = r"[\w!\-_\.\*\'\(\)\%]"
S3_FILE_ID_RE = rf"^({_SAFE_S3_FILE_NAME_RE}+?)\/({_SAFE_S3_FILE_NAME_RE}+?)\/({_SAFE_S3_FILE_NAME_RE}+?)$"

S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID = "UNDEFINED/EXTERNALID"


MAX_LINK_CHUNK_BYTE_SIZE: Final[dict[LinkType, ByteSize]] = {
    LinkType.PRESIGNED: PRESIGNED_LINK_MAX_SIZE,
    LinkType.S3: S3_MAX_FILE_SIZE,
}

MAX_CONCURRENT_S3_TASKS: Final[int] = 4


# REST API ----------------------------
MAX_CONCURRENT_REST_CALLS: Final[int] = 10

# DATABASE ----------------------------
MAX_CONCURRENT_DB_TASKS: Final[int] = 2


EXPAND_DIR_MAX_ITEM_COUNT: Final[int] = 1000
