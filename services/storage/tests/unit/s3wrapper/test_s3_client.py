# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import filecmp
import os
import time
import urllib
import urllib.error
import urllib.request
import uuid
from datetime import timedelta
from typing import Callable

import pytest


@pytest.fixture()
def bucket(s3_client, request):
    bucket_name = "simcore-test"
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)

    def fin():
        s3_client.remove_bucket(bucket_name, delete_contents=True)

    request.addfinalizer(fin)
    return bucket_name


@pytest.fixture(scope="function")
def text_files_factory(tmpdir_factory) -> Callable:
    def _create_files(N):
        filepaths = []
        for _i in range(N):
            name = str(uuid.uuid4())
            filepath = os.path.normpath(
                str(tmpdir_factory.mktemp("data").join(name + ".txt"))
            )
            with open(filepath, "w") as fout:
                fout.write("Hello world\n")
            filepaths.append(filepath)

        return filepaths

    return _create_files


def test_create_remove_bucket(s3_client):
    bucket_name = "simcore-test"
    assert s3_client.create_bucket(bucket_name)
    assert s3_client.exists_bucket(bucket_name)
    s3_client.remove_bucket(bucket_name, delete_contents=True)
    assert not s3_client.exists_bucket(bucket_name)


def test_create_remove_bucket_with_contents(s3_client, text_files_factory):
    bucket_name = "simcore-test"
    assert s3_client.create_bucket(bucket_name)
    assert s3_client.exists_bucket(bucket_name)
    object_name = "dummy"
    filepath = text_files_factory(1)[0]
    assert s3_client.upload_file(bucket_name, object_name, filepath)
    assert s3_client.remove_bucket(bucket_name, delete_contents=False)
    assert s3_client.exists_bucket(bucket_name)
    s3_client.remove_bucket(bucket_name, delete_contents=True)
    assert not s3_client.exists_bucket(bucket_name)


def test_file_upload_download(s3_client, bucket, text_files_factory):
    filepath = text_files_factory(1)[0]
    object_name = "1"
    assert s3_client.upload_file(bucket, object_name, filepath)
    filepath2 = filepath + ".rec"
    assert s3_client.download_file(bucket, object_name, filepath2)
    assert filecmp.cmp(filepath2, filepath)


def test_file_upload_meta_data(s3_client, bucket, text_files_factory):
    filepath = text_files_factory(1)[0]
    object_name = "1"
    _id = uuid.uuid4()
    metadata = {"user": "guidon", "node_id": str(_id), "boom-boom": str(42.0)}

    assert s3_client.upload_file(bucket, object_name, filepath, metadata=metadata)

    metadata2 = s3_client.get_metadata(bucket, object_name)

    assert metadata2["X-Amz-Meta-User"] == "guidon"
    assert metadata2["X-Amz-Meta-Node_id"] == str(_id)
    assert metadata2["X-Amz-Meta-Boom-Boom"] == str(42.0)


def test_sub_folders(s3_client, bucket, text_files_factory):
    bucket_sub_folder = str(uuid.uuid4())
    filepaths = text_files_factory(3)
    counter = 1
    for f in filepaths:
        object_name = bucket_sub_folder + "/" + str(counter)
        assert s3_client.upload_file(bucket, object_name, f)
        counter += 1


def test_presigned_put(s3_client, bucket, text_files_factory):
    filepath = text_files_factory(1)[0]
    object_name = "my_file"
    url = s3_client.create_presigned_put_url(bucket, object_name)
    with open(filepath, "rb") as fp:
        d = fp.read()
        req = urllib.request.Request(url, data=d, method="PUT")
        with urllib.request.urlopen(req) as _f:
            pass

    filepath2 = filepath + ".rec"
    assert s3_client.download_file(bucket, object_name, filepath2)
    assert filecmp.cmp(filepath2, filepath)


def test_presigned_put_expired(s3_client, bucket, text_files_factory):
    filepath = text_files_factory(1)[0]
    object_name = "my_file"
    url = s3_client.create_presigned_put_url(bucket, object_name, timedelta(seconds=1))
    time.sleep(2)
    failed = False
    with open(filepath, "rb") as fp:
        d = fp.read()
        req = urllib.request.Request(url, data=d, method="PUT")
        try:
            # pylint: disable=consider-using-with
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as _ex:
            failed = True
    assert failed


def test_presigned_get(s3_client, bucket, text_files_factory):
    filepath = text_files_factory(1)[0]
    filepath2 = filepath + "."
    object_name = "bla"
    assert s3_client.upload_file(bucket, object_name, filepath)
    url = s3_client.create_presigned_get_url(bucket, object_name)
    urllib.request.urlretrieve(url, filepath2)

    assert filecmp.cmp(filepath2, filepath)


def test_presigned_get_expired(s3_client, bucket, text_files_factory):
    filepath = text_files_factory(1)[0]
    filepath2 = filepath + "."
    object_name = "bla"
    assert s3_client.upload_file(bucket, object_name, filepath)
    url = s3_client.create_presigned_get_url(bucket, object_name, timedelta(seconds=1))
    time.sleep(2)
    failed = False
    try:
        urllib.request.urlretrieve(url, filepath2)
    except urllib.error.HTTPError as _ex:
        failed = True

    assert failed


def test_object_exists(s3_client, bucket, text_files_factory):
    files = text_files_factory(2)
    file1 = files[0]
    file2 = files[1]
    object_name = "level1"
    assert s3_client.upload_file(bucket, object_name, file1)
    assert s3_client.exists_object(bucket, object_name, False)
    object_name = "leve1/level2"
    assert s3_client.upload_file(bucket, object_name, file2)
    assert not s3_client.exists_object(bucket, object_name, False)
    assert s3_client.exists_object(bucket, object_name, True)


def test_copy_object(s3_client, bucket, text_files_factory):
    files = text_files_factory(1)
    file = files[0]
    object_name = "original"
    assert s3_client.upload_file(bucket, object_name, file)
    assert s3_client.exists_object(bucket, object_name, False)
    copied_object = "copy"
    assert s3_client.copy_object(bucket, copied_object, bucket, object_name)
    assert s3_client.exists_object(bucket, copied_object, False)


def test_list_objects(s3_client, bucket, text_files_factory):
    files = text_files_factory(2)
    file1 = files[0]
    file2 = files[1]
    object_name = "level1/level2/1"
    assert s3_client.upload_file(bucket, object_name, file1)
    object_name = "level2/level2/2"
    assert s3_client.upload_file(bucket, object_name, file2)

    listed_objects = s3_client.list_objects(bucket)
    for s3_obj in listed_objects:
        assert s3_obj.object_name in ("level1/", "level2/")

    listed_objects = s3_client.list_objects(bucket, prefix="level1")
    for s3_obj in listed_objects:
        assert s3_obj.object_name == "level1/"

    listed_objects = s3_client.list_objects(bucket, prefix="level1", recursive=True)
    for s3_obj in listed_objects:
        assert s3_obj.object_name == "level1/level2/1"

    listed_objects = s3_client.list_objects(bucket, recursive=True)
    for s3_obj in listed_objects:
        assert s3_obj.object_name in ("level1/level2/1", "level2/level2/2")
