import os
from pathlib import Path
import shutil
import logging
import tempfile
import tenacity
from simcore_sdk.config.s3 import Config as s3_config
from simcore_sdk.nodeports import exceptions
from s3wrapper.s3_client import S3Client

_LOGGER = logging.getLogger(__name__)
_INTERNAL_DIR = os.path.join(tempfile.gettempdir(), "simcorefiles")

class S3Settings:
    def __init__(self):
        _LOGGER.debug("Initialise S3 connection")
        self._config = s3_config()
        self.client = S3Client(endpoint=self._config.endpoint,
            access_key=self._config.access_key, secret_key=self._config.secret_key)
        self.bucket = self._config.bucket_name
        self.client.create_bucket(self.bucket)
        _LOGGER.debug("Initialised S3 connection")

@tenacity.retry(stop=tenacity.stop_after_attempt(3) or tenacity.stop_after_delay(10))
def __download_fromS3(s3_client, s3_bucket, s3_object_name, file_path):
    _LOGGER.debug('Downloading from  S3 %s/%s to %s', s3_bucket, s3_object_name, file_path)    
    success = s3_client.download_file(s3_bucket, s3_object_name, file_path)
    if not success:
        raise exceptions.S3TransferError("could not retrieve file from %s/%s" %(s3_bucket, s3_object_name))
    
    _LOGGER.debug('Downloaded from bucket %s, object %s to %s successfully', s3_bucket, s3_object_name, file_path)

def download_folder_from_s3(node_uuid, node_key, folder_name):
    _LOGGER.debug("Trying to download from S3: node uuid %s, key %s, file name %s", node_uuid, node_key, folder_name)
    s3_object_url =  __encode_s3_url(node_uuid=node_uuid, node_key=node_key)
    s3 = S3Settings()

    folder_path = Path(_INTERNAL_DIR, folder_name)
    if folder_path.exists():
        # remove the folder recursively
        shutil.rmtree(folder_path)

    # get the subobjects
    s3_objects = s3.client.list_objects(bucket_name=s3.bucket, prefix=s3_object_url, recursive=True)
    for obj in s3_objects:
        file_name = Path(obj.object_name).relative_to(s3_object_url)
        full_file_path = folder_path / file_name
        __download_fromS3(s3.client, s3.bucket, obj.object_name, str(full_file_path))    
    
    return folder_path


def download_file_from_S3(node_uuid, node_key, file_name):
    _LOGGER.debug("Trying to download from S3: node uuid %s, key %s, file name %s", node_uuid, node_key, file_name)
    s3_object_url =  __encode_s3_url(node_uuid=node_uuid, node_key=node_key)
    s3 = S3Settings()

    # here we add an extension to circumvent an error when downloading the file under Windows OS
    file_path = Path(_INTERNAL_DIR, file_name, file_name)
    if file_path.suffix == "":
        file_path = file_path.with_suffix(".simcore")
    if file_path.exists():
        # remove the file
        file_path.unlink()
        
    __download_fromS3(s3.client, s3.bucket, s3_object_url, str(file_path))    
    return file_path
    
@tenacity.retry(stop=tenacity.stop_after_attempt(3) or tenacity.stop_after_delay(10))
def __upload_to_s3(s3_client, s3_bucket, s3_object_name, file_path):
    _LOGGER.debug('Uploading to S3 %s/%s from %s', s3_bucket, s3_object_name, file_path)    
    success = s3_client.upload_file(s3_bucket, s3_object_name, file_path)
    if not success:
        raise exceptions.S3TransferError("could not upload file %s to %s/%s" %(file_path, s3_bucket, s3_object_name))
    
    _LOGGER.debug('Uploaded to s3 %s/%s from %s successfully', s3_bucket, s3_object_name, file_path)

def upload_file_to_s3(node_uuid, node_key, file_path):
    _LOGGER.debug("Trying to upload file to S3: node uuid %s, key %s, file path %s", node_uuid, node_key, file_path)
    s3_object_url =  __encode_s3_url(node_uuid=node_uuid, node_key=node_key)
    s3 = S3Settings()
    __upload_to_s3(s3.client, s3.bucket, s3_object_url, file_path)
    return s3_object_url
    

def upload_folder_to_s3(node_uuid, node_key, folder_path):
    _LOGGER.debug("Trying to upload folder to S3: node uuid %s, key %s, folder path %s", node_uuid, node_key, folder_path)
    s3_object_base_url =  __encode_s3_url(node_uuid=node_uuid, node_key=node_key)
    s3 = S3Settings()
    path = Path(folder_path)
    for path_child in path.iterdir():
        if path_child.is_file():
            s3_object_url = (Path(s3_object_base_url) / path_child.name).as_posix()
            __upload_to_s3(s3.client, s3.bucket, s3_object_url, path_child)
    return s3_object_base_url

def __encode_s3_url(node_uuid, node_key):
    return Path(os.environ.get('SIMCORE_PIPELINE_ID', default="undefined"), node_uuid, node_key).as_posix()