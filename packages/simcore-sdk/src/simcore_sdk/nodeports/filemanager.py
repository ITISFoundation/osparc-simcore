import os
import logging
import tempfile
import tenacity
from simcore_sdk.config.s3 import Config as s3_config
from s3wrapper.s3_client import S3Client

_LOGGER = logging.getLogger(__name__)
_INTERNAL_DIR = os.path.join(tempfile.gettempdir(), "simcorefiles")

class S3Settings(object):
    def __init__(self):
        self._config = s3_config()
        self.client = S3Client(endpoint=self._config.endpoint,
            access_key=self._config.access_key, secret_key=self._config.secret_key)
        self.bucket = self._config.bucket_name
        self.client.create_bucket(self.bucket)

@tenacity.retry(stop=tenacity.stop_after_attempt(3) | tenacity.stop_after_delay(10))
def __download_fromS3(s3_client, s3_bucket, s3_object_name, file_path):
    
    success = s3_client.download_file(s3_bucket, s3_object_name, file_path)
    if not success:
        raise Exception("could not retrieve file")
    
    _LOGGER.debug('Downloaded from bucket %s, object %s to %s successfully', s3_bucket, s3_object_name, file_path)

def download_from_S3_if_newer(s3_object_name, object_timestamp, file_name):
    _LOGGER.debug("Initialise S3 connection")
    _s3 = S3Settings()
    _LOGGER.debug("Initialised S3 connection")
    s3_object_name = os.path.join(os.environ.get('PIPELINE_NODE_ID'), *s3_object_name)
    s3_object_name = s3_object_name.replace("\\", "/")
    file_path = os.path.join(_INTERNAL_DIR, file_name, object_timestamp, file_name +".simcore")
    _LOGGER.debug('Downloading from  S3 %s/%s to %s', _s3.bucket, s3_object_name, file_path)    
    __download_fromS3(_s3.client, _s3.bucket, s3_object_name, file_path)    
    return file_path
    