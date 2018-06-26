import filecmp
import os
import uuid

import pytest
import urllib
import time
from datetime import timedelta

from s3wrapper.s3_client import S3Client

import requests

# pylint:disable=unused-import
from pytest_docker import docker_ip, docker_services


# pylint:disable=redefined-outer-name

def is_responsive(url, code=200):
    """Check if something responds to ``url``."""
    try:
        response = requests.get(url)
        if response.status_code == code:
            return True
    except requests.exceptions.RequestException as _e:
        pass
    return False

@pytest.fixture(scope="module")
def s3_client(docker_ip, docker_services):
    """wait for minio to be up"""

    # Build URL to service listening on random port.
    url = 'http://%s:%d/' % (
        docker_ip,
        docker_services.port_for('minio', 9000),
    )

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: is_responsive(url, 403),
        timeout=30.0,
        pause=0.1,
    )

    # Contact the service.
    response = requests.get(url)
    assert response.status_code == 403

    endpoint = '{ip}:{port}'.format(ip=docker_ip, port=docker_services.port_for('minio', 9000))
    access_key = "12345678"
    secret_key = "12345678"
    secure = False
    s3_client = S3Client(endpoint, access_key, secret_key, secure)
    return s3_client

@pytest.fixture()
def bucket(s3_client, request):
    bucket_name = "simcore-test"
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)
    def fin():
        s3_client.remove_bucket(bucket_name, delete_contents=True)
    request.addfinalizer(fin)
    return bucket_name

@pytest.fixture(scope="function")
def text_files(tmpdir_factory):
    def _create_files(N):
        filepaths = []
        for _i in range(N):
            name = str(uuid.uuid4())
            filepath = os.path.normpath(str(tmpdir_factory.mktemp('data').join(name + ".txt")))
            with open(filepath, 'w') as fout:
                fout.write("Hello world\n")
            filepaths.append(filepath)

        return filepaths
    return _create_files

@pytest.mark.enable_travis
def test_create_remove_bucket(s3_client):
    bucket_name = "simcore-test"
    assert s3_client.create_bucket(bucket_name)
    assert s3_client.exists_bucket(bucket_name)
    s3_client.remove_bucket(bucket_name, delete_contents=True)
    assert not s3_client.exists_bucket(bucket_name)

@pytest.mark.enable_travis
def test_create_remove_bucket_with_contents(s3_client, text_files):
    bucket_name = "simcore-test"
    assert s3_client.create_bucket(bucket_name)
    assert s3_client.exists_bucket(bucket_name)
    object_name = "dummy"
    filepath = text_files(1)[0]
    assert s3_client.upload_file(bucket_name, object_name, filepath)
    assert s3_client.remove_bucket(bucket_name, delete_contents=False)
    assert s3_client.exists_bucket(bucket_name)
    s3_client.remove_bucket(bucket_name, delete_contents=True)
    assert not s3_client.exists_bucket(bucket_name)

@pytest.mark.enable_travis
def test_file_upload_download(s3_client, bucket, text_files):
    filepath = text_files(1)[0]
    object_name = "1"
    assert s3_client.upload_file(bucket, object_name, filepath)
    filepath2 = filepath + ".rec"
    assert s3_client.download_file(bucket, object_name, filepath2)
    assert filecmp.cmp(filepath2, filepath)

@pytest.mark.enable_travis
def test_file_upload_meta_data(s3_client, bucket, text_files):
    filepath = text_files(1)[0]
    object_name = "1"
    _id = uuid.uuid4()
    metadata = {'user' : 'guidon', 'node_id' : str(_id), 'boom-boom' : str(42.0)}

    assert s3_client.upload_file(bucket, object_name, filepath, metadata=metadata)

    metadata2 = s3_client.get_metadata(bucket, object_name)

    assert metadata2["User"] == 'guidon'
    assert metadata2["Node_id"] == str(_id)
    assert metadata2["Boom-Boom"] == str(42.0)

@pytest.mark.enable_travis
def test_sub_folders(s3_client, bucket, text_files):
    bucket_sub_folder = str(uuid.uuid4())
    filepaths = text_files(3)
    counter = 1
    for f in filepaths:
        object_name = bucket_sub_folder + "/" + str(counter)
        assert s3_client.upload_file(bucket, object_name, f)
        counter += 1

@pytest.mark.enable_travis
def test_search(s3_client, bucket, text_files):
    metadata = [{'User' : 'alpha'}, {'User' : 'beta' }, {'User' : 'gamma'}]

    for i in range(3):
        bucket_sub_folder = "Folder"+ str(i+1)

        filepaths = text_files(3)
        counter = 0
        for f in filepaths:
            object_name = bucket_sub_folder + "/" + "Data" + str(counter)
            assert s3_client.upload_file(bucket, object_name, f, metadata=metadata[counter])
            counter += 1

    query = "DATA1"
    results = s3_client.search(bucket, query, recursive=False, include_metadata=False)
    assert not results

    results = s3_client.search(bucket, query, recursive=True, include_metadata=False)
    assert len(results) == 3

    query = "alpha"
    results = s3_client.search(bucket, query, recursive=True, include_metadata=True)
    assert len(results) == 3

    query = "dat*"
    results = s3_client.search(bucket, query, recursive=True, include_metadata=False)
    assert len(results) == 9

@pytest.mark.enable_travis
def test_presigned_put(s3_client, bucket, text_files):
    filepath = text_files(1)[0]
    object_name = "my_file"
    url = s3_client.create_presigned_put_url(bucket, object_name)
    with open(filepath, 'rb') as fp:
        d = fp.read()
        req = urllib.request.Request(url, data=d, method='PUT')
        with urllib.request.urlopen(req) as _f:
            pass

    filepath2 = filepath + ".rec"
    assert s3_client.download_file(bucket, object_name, filepath2)
    assert filecmp.cmp(filepath2, filepath)

@pytest.mark.enable_travis
def test_presigned_put_expired(s3_client, bucket, text_files):
    filepath = text_files(1)[0]
    object_name = "my_file"
    url = s3_client.create_presigned_put_url(bucket, object_name, timedelta(seconds=1))
    time.sleep(2)
    failed = False
    with open(filepath, 'rb') as fp:
        d = fp.read()
        req = urllib.request.Request(url, data=d, method='PUT')
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as _ex:
            failed = True
    assert failed


@pytest.mark.enable_travis
def test_presigned_get(s3_client, bucket, text_files):
    filepath = text_files(1)[0]
    filepath2 = filepath + "."
    object_name = "bla"
    assert s3_client.upload_file(bucket, object_name, filepath)
    url = s3_client.create_presigned_get_url(bucket, object_name)
    urllib.request.urlretrieve(url, filepath2)

    assert filecmp.cmp(filepath2, filepath)

@pytest.mark.enable_travis
def test_presigned_get_expired(s3_client, bucket, text_files):
    filepath = text_files(1)[0]
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

@pytest.mark.enable_travis
def test_object_exists(s3_client, bucket, text_files):
    files = text_files(2)
    file1 = files[0]
    file2 = files[1]
    object_name = "level1"
    assert s3_client.upload_file(bucket, object_name, file1)
    assert s3_client.exists_object(bucket, object_name, False)
    object_name = "leve1/level2"
    assert s3_client.upload_file(bucket, object_name, file2)
    assert not s3_client.exists_object(bucket, object_name, False)
    assert s3_client.exists_object(bucket, object_name, True)

@pytest.mark.enable_travis
def test_copy_object(s3_client, bucket, text_files):
    files = text_files(1)
    file = files[0]
    object_name = "original"
    assert s3_client.upload_file(bucket, object_name, file)
    assert s3_client.exists_object(bucket, object_name, False)
    copied_object = "copy"
    assert s3_client.copy_object(bucket, copied_object, bucket + "/" + object_name)
    assert s3_client.exists_object(bucket, copied_object, False)

def test_list_objects(s3_client, bucket, text_files):
    files = text_files(2)
    file1 = files[0]
    file2 = files[1]
    object_name = "level1/level2/1"
    assert s3_client.upload_file(bucket, object_name, file1)
    object_name = "level2/level2/2"
    assert s3_client.upload_file(bucket, object_name, file2)

    listed_objects = s3_client.list_objects(bucket)
    for s3_obj in listed_objects:
        assert s3_obj.object_name == "level1/" or s3_obj.object_name == "level2/"

    listed_objects = s3_client.list_objects(bucket, prefix="level1")
    for s3_obj in listed_objects:
        assert s3_obj.object_name == "level1/"

    listed_objects = s3_client.list_objects(bucket, prefix="level1", recursive=True)
    for s3_obj in listed_objects:
        assert s3_obj.object_name == "level1/level2/1"

    listed_objects = s3_client.list_objects(bucket, recursive=True)
    for s3_obj in listed_objects:
        assert s3_obj.object_name == "level1/level2/1" or s3_obj.object_name == "level2/level2/2"
