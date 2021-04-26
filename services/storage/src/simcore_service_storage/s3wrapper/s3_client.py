import logging
import re
from datetime import timedelta

from minio import Minio
from minio.commonconfig import CopySource
from minio.deleteobjects import DeleteObject
from minio.error import MinioException

log = logging.getLogger(__name__)


class S3Client:
    """Wrapper around minio"""

    def __init__(
        self,
        endpoint: str,
        access_key: str = None,
        secret_key: str = None,
        secure: bool = False,
    ):
        self.__metadata_prefix = "x-amz-meta-"
        self.client = None
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self.endpoint_url = ("https://" if secure else "http://") + endpoint
        try:
            self.client = Minio(
                endpoint, access_key=access_key, secret_key=secret_key, secure=secure
            )
        except MinioException as _err:
            log.exception("Could not create minio client")

    def __remove_objects_recursively(self, bucket_name):
        delete_object_list = map(
            lambda x: DeleteObject(x.object_name),
            self.list_objects(bucket_name, prefix=None, recursive=True),
        )

        self.remove_objects(bucket_name, delete_object_list)

    def create_bucket(self, bucket_name, delete_contents_if_exists=False):
        try:
            if not self.exists_bucket(bucket_name):
                self.client.make_bucket(bucket_name)
            elif delete_contents_if_exists:
                return self.__remove_objects_recursively(bucket_name)

        except MinioException as _err:
            log.exception("Could not create bucket")
            return False
        # it probably already exists and is
        return True

    def remove_bucket(self, bucket_name, delete_contents=False):
        try:
            if self.exists_bucket(bucket_name):
                if delete_contents:
                    self.__remove_objects_recursively(bucket_name)
                    self.client.remove_bucket(bucket_name)
        except MinioException as _err:
            log.exception("Could not remove bucket")
            return False
        return True

    def exists_bucket(self, bucket_name):
        try:
            return self.client.bucket_exists(bucket_name)
        except MinioException as _err:
            log.exception("Could not check bucket for existence")

        return False

    def list_buckets(self):
        try:
            return self.client.list_buckets()
        except MinioException as _err:
            log.exception("Could not list bucket")

        return []

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
            self.client.fput_object(
                bucket_name, object_name, filepath, metadata=_metadata
            )
        except MinioException as _err:
            log.exception("Could not upload file")
            return False
        return True

    def download_file(self, bucket_name, object_name, filepath):
        try:
            self.client.fget_object(bucket_name, object_name, filepath)
        except MinioException as _err:
            log.exception("Could not download file")
            return False
        return True

    def get_metadata(self, bucket_name, object_name):
        try:
            obj = self.client.stat_object(bucket_name, object_name)
            _metadata = obj.metadata
            metadata = {}
            for key in _metadata.keys():
                _key = key[len(self.__metadata_prefix) :]
                metadata[_key] = _metadata[key]
            return metadata

        except MinioException as _err:
            log.exception("Could not get metadata")

        return {}

    def list_objects(self, bucket_name, prefix=None, recursive=False):
        try:
            return self.client.list_objects(
                bucket_name, prefix=prefix, recursive=recursive
            )
        except MinioException as _err:
            log.exception("Could not list objects")

        return []

    def list_objects_v2(self, bucket_name, recursive=False):
        try:
            return self.client.list_objects_v2(bucket_name, recursive=recursive)
        except MinioException as _err:
            log.exception("Could not list objects")

        return []

    def remove_objects(self, bucket_name, objects):
        try:
            for del_err in self.client.remove_objects(bucket_name, objects):
                msg = "Deletion Error: {}".format(del_err)
                log.debug(msg)
        except MinioException as _err:
            log.exception("Could remove objects")
            return False
        return True

    def exists_object(self, bucket_name, object_name, recursive=False):
        """This seems to be pretty heavy, should be used with care"""
        try:
            objects = self.list_objects(bucket_name, recursive=recursive)
            for obj in objects:
                if obj.object_name == object_name:
                    return True
        except MinioException as _err:
            log.exception("Could check object for existence")
            return False
        return False

    def search(self, bucket_name, query, recursive=True, include_metadata=False):
        results = []
        objs = self.list_objects(bucket_name, recursive=recursive)

        _query = re.compile(query, re.IGNORECASE)

        for obj in objs:
            if _query.search(obj.object_name):
                results.append(obj)
            if include_metadata:
                metadata = self.get_metadata(bucket_name, obj.object_name)
                for key in metadata.keys():
                    if _query.search(key) or _query.search(metadata[key]):
                        results.append(obj)

        for r in results:
            msg = "Object {} in bucket {} matches query {}".format(
                r.object_name, r.bucket_name, query
            )
            log.debug(msg)

        return results

    def create_presigned_put_url(self, bucket_name, object_name, dt=timedelta(days=3)):
        try:
            return self.client.presigned_put_object(
                bucket_name, object_name, expires=dt
            )

        except MinioException as _err:
            log.exception("Could create presigned put url")

        return ""

    def create_presigned_get_url(self, bucket_name, object_name, dt=timedelta(days=3)):
        try:
            return self.client.presigned_get_object(
                bucket_name, object_name, expires=dt
            )

        except MinioException as _err:
            log.exception("Could create presigned get url")

        return ""

    def copy_object(self, bucket_name, to_object_name, from_object_name):
        """ Copies from_object_name -> to_object_name within the same bucket """
        result = self.client.copy_object(
            bucket_name=bucket_name,
            object_name=to_object_name,
            source=CopySource(bucket_name, from_object_name),
        )
        log.debug(
            "%s:%s -> %s:%s: %s",
            bucket_name,
            from_object_name,
            bucket_name,
            to_object_name,
            result,
        )
