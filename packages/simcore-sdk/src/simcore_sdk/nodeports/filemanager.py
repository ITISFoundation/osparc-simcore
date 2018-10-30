import logging
from pathlib import Path

import tenacity

from s3wrapper.s3_client import S3Client
from simcore_sdk.config.s3 import Config as s3_config
from simcore_sdk.nodeports import exceptions

log = logging.getLogger(__name__)


class S3Settings:
    def __init__(self):
        log.debug("Initialise S3 connection")
        self._config = s3_config()
        self.client = S3Client(endpoint=self._config.endpoint,
            access_key=self._config.access_key, secret_key=self._config.secret_key)
        self.bucket = self._config.bucket_name
        self.client.create_bucket(self.bucket)
        log.debug("Initialised S3 connection")

@tenacity.retry(retry=tenacity.retry_if_exception_type(exceptions.S3TransferError),
            reraise=True, 
            stop=tenacity.stop_after_attempt(3) or tenacity.stop_after_delay(10),
            before_sleep=tenacity.before_sleep_log(log, logging.DEBUG))
def __download_fromS3(s3_client, s3_bucket, s3_object_name, file_path):
    log.debug('Checking if object exists in S3 %s/%s', s3_bucket, s3_object_name)
    if not s3_client.exists_object(s3_bucket, s3_object_name, True):
        raise exceptions.S3InvalidPathError(s3_bucket, s3_object_name)

    log.debug('Downloading from  S3 %s/%s to %s', s3_bucket, s3_object_name, file_path)
    success = s3_client.download_file(s3_bucket, s3_object_name, file_path)
    if not success:
        raise exceptions.S3TransferError("could not retrieve file from %s/%s" %(s3_bucket, s3_object_name))

    log.debug('Downloaded from bucket %s, object %s to %s successfully', s3_bucket, s3_object_name, file_path)

def download_file_from_S3(store: str, s3_object_name: str, file_path: Path):
    log.debug("Trying to download from S3: store %s, s3 object %s, file name %s", store, s3_object_name, file_path)
    s3 = S3Settings()

    if "s3-z43" in store:
        s3_object_url = Path(s3_object_name).as_posix()
        # sometimes the path contains the bucket name. this needs to be removed.
        log.debug("s3 object %s, bucket %s", s3_object_url, s3.bucket)
        if str(s3_object_url).startswith(s3.bucket):
            s3_object_url = "".join(Path(s3_object_url).parts[1:])

        # remove an already existing file if present
        if file_path.exists():
            file_path.unlink()

        __download_fromS3(s3.client, s3.bucket, s3_object_url, str(file_path))
        return file_path

    raise exceptions.S3InvalidStore(store)

@tenacity.retry(retry=tenacity.retry_if_exception_type(exceptions.S3TransferError),
            reraise=True, 
            stop=tenacity.stop_after_attempt(3) or tenacity.stop_after_delay(10),
            before_sleep=tenacity.before_sleep_log(log, logging.DEBUG))
def __upload_to_s3(s3_client, s3_bucket, s3_object_name, file_path):
    log.debug('Uploading to S3 %s/%s from %s', s3_bucket, s3_object_name, file_path)
    success = s3_client.upload_file(s3_bucket, s3_object_name, file_path)
    if not success:
        raise exceptions.S3TransferError("could not upload file %s to %s/%s" %(file_path, s3_bucket, s3_object_name))

    log.debug('Uploaded to s3 %s/%s from %s successfully', s3_bucket, s3_object_name, file_path)

def upload_file_to_s3(store:str, s3_object:str, file_path:Path):
    log.debug("Trying to upload file to S3: store %s, s3ovject %s, file path %s", store, s3_object, file_path)
    s3 = S3Settings()
    __upload_to_s3(s3.client, s3.bucket, s3_object, file_path)
    return s3_object
