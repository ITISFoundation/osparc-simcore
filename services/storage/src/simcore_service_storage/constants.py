from servicelib.aiohttp import application_keys

RETRY_WAIT_SECS = 2
MAX_CHUNK_SIZE = 1024
MINUTE = 60

APP_CONFIG_KEY = application_keys.APP_CONFIG_KEY  # app-storage-key for config object

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

# REST API ----------------------------
APP_OPENAPI_SPECS_KEY = (
    application_keys.APP_OPENAPI_SPECS_KEY
)  # app-storage-key for openapi specs object


# DATABASE ----------------------------
APP_DB_ENGINE_KEY = f"{__name__}.db_engine"


# DATA STORAGE MANAGER ----------------------------------
APP_DSM_KEY = f"{__name__}.DSM"
APP_S3_KEY = f"{__name__}.S3_CLIENT"
