#
# SEE https://docs.min.io/docs/python-client-api-reference.html
#
import logging
from datetime import timedelta
from typing import Iterator, List, Optional

from minio import Minio
from minio.commonconfig import CopySource
from minio.datatypes import Object
from minio.deleteobjects import DeleteError, DeleteObject
from minio.error import MinioException
from minio.helpers import ObjectWriteResult

log = logging.getLogger(__name__)


class MinioClientWrapper:
    """Wrapper around minio"""

    def __init__(
        self,
        endpoint: str,
        access_key: str = None,
        secret_key: str = None,
        secure: bool = False,
    ):
        self.__metadata_prefix = "x-amz-meta-"
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self.endpoint_url = ("https://" if secure else "http://") + endpoint
        try:
            self._minio = Minio(
                endpoint, access_key=access_key, secret_key=secret_key, secure=secure
            )
        except MinioException:
            logging.exception("Could not create minio client")
            raise

    def __remove_objects_recursively(self, bucket_name):
        to_del = [
            obj.object_name for obj in self.list_objects(bucket_name, recursive=True)
        ]
        self.remove_objects(bucket_name, to_del)

    def create_bucket(self, bucket_name, delete_contents_if_exists=False):
        try:
            if not self.exists_bucket(bucket_name):
                self._minio.make_bucket(bucket_name)
            elif delete_contents_if_exists:
                return self.__remove_objects_recursively(bucket_name)

        except MinioException:
            logging.exception("Could not create bucket")
            return False
        # it probably already exists and is
        return True

    def remove_bucket(self, bucket_name, delete_contents=False):
        try:
            if self.exists_bucket(bucket_name):
                if delete_contents:
                    self.__remove_objects_recursively(bucket_name)
                    self._minio.remove_bucket(bucket_name)
        except MinioException:
            logging.exception("Could not remove bucket")
            return False
        return True

    def exists_bucket(self, bucket_name):
        try:
            return self._minio.bucket_exists(bucket_name)
        except MinioException:
            logging.exception("Could not check bucket for existence")

        return False

    def upload_file(self, bucket_name, object_name, filepath, metadata=None):
        """Note

        metadata are special, you need to use the
        'X-Amz-Meta' standard, i.e:
            - key and value must be strings
            - and the keys are case insensitive:

                key1 -- > Key1
                key_one --> Key_one
                key-one --> Key-One

        """
        try:
            _metadata = {}
            if metadata is not None:
                for key in metadata.keys():
                    _metadata[self.__metadata_prefix + key] = metadata[key]
            self._minio.fput_object(
                bucket_name, object_name, filepath, metadata=_metadata
            )
        except MinioException:
            logging.exception("Could not upload file")
            return False
        return True

    def download_file(self, bucket_name, object_name, filepath):
        try:
            self._minio.fget_object(bucket_name, object_name, filepath)
        except MinioException:
            logging.exception("Could not download file")
            return False
        return True

    def get_metadata(self, bucket_name, object_name):
        try:
            obj = self._minio.stat_object(bucket_name, object_name)
            assert obj.metadata  # nosec
            return dict(obj.metadata)

        except MinioException:
            logging.exception("Could not get metadata")

        return {}

    def list_objects(
        self, bucket_name: str, prefix: Optional[str] = None, recursive: bool = False
    ) -> Iterator[Object]:
        try:
            return self._minio.list_objects(
                bucket_name=bucket_name, prefix=prefix, recursive=recursive
            )
        except MinioException:
            logging.exception("Could not list objects")

        return []

    def remove_objects(self, bucket_name: str, objects: List[str]):
        try:
            delete = [DeleteObject(name, version_id=None) for name in objects]
            iter_errors: Iterator[DeleteError] = self._minio.remove_objects(
                bucket_name, delete
            )
            for err in iter_errors:
                log.error(
                    "Failed to delete '%s' [version=%s]: %s (code: %s)",
                    err.name,
                    err.version_id,
                    err.message,
                    err.code,
                )

        except MinioException:
            logging.exception("Could remove objects")
            return False
        return True

    def exists_object(self, bucket_name, object_name, recursive=False):
        """This seems to be pretty heavy, should be used with care"""
        try:
            for obj in self.list_objects(bucket_name, recursive=recursive):
                if obj.object_name == object_name:
                    return True
        except MinioException:
            logging.exception("Could check object for existence")
            return False
        return False

    def create_presigned_put_url(self, bucket_name, object_name, dt=timedelta(days=3)):
        try:
            return self._minio.presigned_put_object(
                bucket_name, object_name, expires=dt
            )

        except MinioException:
            logging.exception("Could create presigned put url")

        return ""

    def create_presigned_get_url(self, bucket_name, object_name, dt=timedelta(days=3)):
        try:
            return self._minio.presigned_get_object(
                bucket_name, object_name, expires=dt
            )

        except MinioException:
            logging.exception("Could create presigned get url")

        return ""

    def copy_object(
        self,
        to_bucket_name: str,
        to_object_name: str,
        from_bucket: str,
        from_object: str,
    ):
        try:
            # ValueError for arguments
            result: ObjectWriteResult = self._minio.copy_object(
                bucket_name=to_bucket_name,
                object_name=to_object_name,
                source=CopySource(from_bucket, from_object),
            )
            return result.bucket_name == to_bucket_name
        except MinioException:
            logging.exception("Could not copy")

        return False
