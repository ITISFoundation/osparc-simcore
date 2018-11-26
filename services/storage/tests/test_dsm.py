# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint: disable=too-many-arguments

import filecmp
import io
import json
import os
import pdb
import urllib
import uuid
from pathlib import Path
from pprint import pprint

import attr
import pytest

import utils
from simcore_service_storage.dsm import DataStorageManager
from simcore_service_storage.models import FileMetaData
from simcore_service_storage.s3 import (DATCORE_STR, SIMCORE_S3_ID,
                                        SIMCORE_S3_STR)
from utils import BUCKET_NAME


def test_mockup(dsm_mockup_db):
    assert len(dsm_mockup_db)==100

# Too many branches (13/12) (too-many-branches)
# pylint: disable=R0912
async def test_dsm_s3(dsm_mockup_db, dsm_fixture):
    id_name_map = {}
    id_file_count = {}
    for d in dsm_mockup_db.keys():
        md = dsm_mockup_db[d]
        if not md.user_id in id_name_map:
            id_name_map[md.user_id] = md.user_name
            id_file_count[md.user_id] = 1
        else:
            id_file_count[md.user_id] = id_file_count[md.user_id] + 1

    dsm = dsm_fixture

    data_as_dict = []
    write_data = False
    # list files for every user
    for _id in id_file_count:
        data = await dsm.list_files(user_id=_id, location=SIMCORE_S3_STR)
        assert len(data) == id_file_count[_id]
        if write_data:
            for d in data:
                data_as_dict.append(attr.asdict(d))

    if write_data:
        with open("example.json", 'w') as _f:
            json.dump(data_as_dict, _f)

    # Get files from bob from the project biology
    bob_id = 0
    for _id in id_name_map.keys():
        if id_name_map[_id] == "bob":
            bob_id = _id
            break
    assert not bob_id == 0

    data = await dsm.list_files(user_id=bob_id, location=SIMCORE_S3_STR, regex="biology")
    bobs_bio_files = []
    for d in dsm_mockup_db.keys():
        md = dsm_mockup_db[d]
        if md.user_id == bob_id and md.project_name == "biology":
            bobs_bio_files.append(md)

    assert len(data) # bad luck with the randomizer
    assert len(data) == len(bobs_bio_files)


    # among bobs bio files, filter by project/node, take first one

    uuid_filter = os.path.join(bobs_bio_files[0].project_id, bobs_bio_files[0].node_id)
    filtered_data = await dsm.list_files(user_id=bob_id, location=SIMCORE_S3_STR, uuid_filter=str(uuid_filter))
    assert filtered_data[0] == bobs_bio_files[0]

    for d in data:
        await dsm.delete_file(user_id=d.user_id, location=SIMCORE_S3_STR, file_uuid=d.file_uuid)

    # now we should have less items
    new_size = 0
    for _id in id_file_count:
        data = await dsm.list_files(user_id=_id, location=SIMCORE_S3_STR)
        new_size = new_size + len(data)

    assert len(dsm_mockup_db) == new_size + len(bobs_bio_files)

def _create_file_meta_for_s3(postgres_url, s3_client, tmp_file):
    utils.create_tables(url=postgres_url)
    bucket_name = BUCKET_NAME
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)


    # create file and upload
    filename = os.path.basename(tmp_file)
    project_id = "22"
    node_id = "1006"
    file_name = filename
    file_uuid = os.path.join(str(project_id), str(node_id), str(file_name))

    d = {   'object_name' : os.path.join(str(project_id), str(node_id), str(file_name)),
            'bucket_name' : bucket_name,
            'file_name' : filename,
            'user_id' : "42",
            'user_name' : "starbucks",
            'location' : SIMCORE_S3_STR,
            'project_id' : project_id,
            'project_name' : "battlestar",
            'node_id' : node_id,
            'node_name' : "this is the name of the node",
            'file_uuid' : file_uuid
        }

    fmd = FileMetaData(**d)

    return fmd

async def test_links_s3(postgres_service_url, s3_client, mock_files_factory, dsm_fixture):
    utils.create_tables(url=postgres_service_url)

    tmp_file = mock_files_factory(1)[0]
    fmd = _create_file_meta_for_s3(postgres_service_url, s3_client, tmp_file)

    dsm = dsm_fixture

    up_url = await dsm.upload_link(fmd.user_id, fmd.file_uuid)
    with io.open(tmp_file, 'rb') as fp:
        d = fp.read()
        req = urllib.request.Request(up_url, data=d, method='PUT')
        with urllib.request.urlopen(req) as _f:
            pass

    tmp_file2 = tmp_file + ".rec"
    user_id = 0
    down_url = await dsm.download_link(user_id, SIMCORE_S3_STR, fmd.file_uuid)

    urllib.request.urlretrieve(down_url, tmp_file2)

    assert filecmp.cmp(tmp_file2, tmp_file)

async def test_copy_s3_s3(postgres_service_url, s3_client, mock_files_factory, dsm_fixture):
    utils.create_tables(url=postgres_service_url)

    tmp_file = mock_files_factory(1)[0]
    fmd = _create_file_meta_for_s3(postgres_service_url, s3_client, tmp_file)

    dsm = dsm_fixture
    data = await dsm.list_files(user_id=fmd.user_id, location=SIMCORE_S3_STR)
    assert len(data) == 0

    # upload the file
    up_url = await dsm.upload_link(fmd.user_id, fmd.file_uuid)
    with io.open(tmp_file, 'rb') as fp:
        d = fp.read()
        req = urllib.request.Request(up_url, data=d, method='PUT')
        with urllib.request.urlopen(req) as _f:
            pass

    data = await dsm.list_files(user_id=fmd.user_id, location=SIMCORE_S3_STR)
    assert len(data) == 1

    from_uuid = fmd.file_uuid
    new_project = "zoology"
    to_uuid = os.path.join(new_project, fmd.node_id, fmd.file_name)
    await dsm.copy_file(user_id=fmd.user_id, dest_location=SIMCORE_S3_STR, dest_uuid=to_uuid, source_location=SIMCORE_S3_STR, source_uuid=from_uuid)

    data = await dsm.list_files(user_id=fmd.user_id, location=SIMCORE_S3_STR)

    assert len(data) == 2

#NOTE: Below tests directly access the datcore platform, use with care!
@pytest.mark.travis
def test_datcore_fixture(datcore_testbucket):
    print(datcore_testbucket)

@pytest.mark.travis
async def test_dsm_datcore(postgres_service_url, dsm_fixture, datcore_testbucket):
    utils.create_tables(url=postgres_service_url)
    dsm = dsm_fixture
    user_id = "0"
    data = await dsm.list_files(user_id=user_id, location=DATCORE_STR)
    # the fixture creates two files
    assert len(data) == 2

    # delete the first one
    fmd_to_delete = data[0]
    print("Deleting", fmd_to_delete.bucket_name, fmd_to_delete.object_name)
    await dsm.delete_file(user_id, DATCORE_STR, fmd_to_delete.file_uuid)

    data = await dsm.list_files(user_id=user_id, location=DATCORE_STR)
    assert len(data) == 1

@pytest.mark.travis
async def test_dsm_s3_to_datcore(postgres_service_url, s3_client, mock_files_factory, dsm_fixture, datcore_testbucket):
    utils.create_tables(url=postgres_service_url)
    tmp_file = mock_files_factory(1)[0]

    fmd = _create_file_meta_for_s3(postgres_service_url, s3_client, tmp_file)

    dsm = dsm_fixture

    up_url = await dsm.upload_link(fmd.user_id, fmd.file_uuid)
    with io.open(tmp_file, 'rb') as fp:
        d = fp.read()
        req = urllib.request.Request(up_url, data=d, method='PUT')
        with urllib.request.urlopen(req) as _f:
            pass

    # given the fmd, upload to datcore
    tmp_file2 = tmp_file + ".fordatcore"
    user_id = "0"
    down_url = await dsm.download_link(user_id, SIMCORE_S3_STR, fmd.file_uuid)
    urllib.request.urlretrieve(down_url, tmp_file2)
    assert filecmp.cmp(tmp_file2, tmp_file)
    # now we have the file locally, upload the file
    await dsm.upload_file_to_datcore(user_id, tmp_file2, datcore_testbucket, fmd)

    data = await dsm.list_files(user_id=user_id, location=DATCORE_STR)

    # there should now be 3 files
    assert len(data) == 3

@pytest.mark.travis
async def test_dsm_datcore_to_local(postgres_service_url, dsm_fixture, mock_files_factory, datcore_testbucket):
    utils.create_tables(url=postgres_service_url)
    dsm = dsm_fixture
    user_id = "0"
    data = await dsm.list_files(user_id=user_id, location=DATCORE_STR)
    assert len(data)

    fmd_to_get = data[0]
    url = await dsm.download_link(user_id, DATCORE_STR, fmd_to_get.file_uuid)

    tmp_file = mock_files_factory(1)[0]
    tmp_file2 = tmp_file + ".fromdatcore"

    urllib.request.urlretrieve(url, tmp_file2)

    assert filecmp.cmp(tmp_file2, tmp_file)

@pytest.mark.travis
async def test_dsm_datcore_to_S3(postgres_service_url, s3_client, dsm_fixture, mock_files_factory, datcore_testbucket):
    utils.create_tables(url=postgres_service_url)
    # create temporary file
    tmp_file = mock_files_factory(1)[0]
    dest_fmd = _create_file_meta_for_s3(postgres_service_url, s3_client, tmp_file)
    user_id = dest_fmd.user_id
    dest_uuid = dest_fmd.file_uuid

    dsm = dsm_fixture

    s3_data = await dsm.list_files(user_id=user_id, location=SIMCORE_S3_STR)
    assert len(s3_data) == 0

    dc_data = await dsm.list_files(user_id=user_id, location=DATCORE_STR)
    assert len(dc_data) == 2
    src_fmd = dc_data[0]

    await dsm.copy_file(user_id=user_id, dest_location=SIMCORE_S3_STR, dest_uuid=dest_uuid, source_location=DATCORE_STR, source_uuid=src_fmd.file_uuid)

    s3_data = await dsm.list_files(user_id=user_id, location=SIMCORE_S3_STR)
    assert len(s3_data) == 1

    # now download the original file
    tmp_file1 = tmp_file + ".fromdatcore"
    down_url_dc = await dsm.download_link(user_id, DATCORE_STR, src_fmd.file_uuid)
    urllib.request.urlretrieve(down_url_dc, tmp_file1)

    # and the one on s3
    tmp_file2 = tmp_file + ".fromS3"
    down_url_s3 = await dsm.download_link(user_id, SIMCORE_S3_STR, dest_uuid)
    urllib.request.urlretrieve(down_url_s3, tmp_file2)

    assert filecmp.cmp(tmp_file1, tmp_file2)

@pytest.mark.travis
async def test_copy_datcore(postgres_service_url, s3_client, dsm_fixture, mock_files_factory, datcore_testbucket):
    utils.create_tables(url=postgres_service_url)

    # the fixture should provide 2 files
    dsm = dsm_fixture
    user_id = "0"
    data = await dsm.list_files(user_id=user_id, location=DATCORE_STR)
    assert len(data) == 2

    # create temporary file and upload to s3
    tmp_file = mock_files_factory(1)[0]
    fmd = _create_file_meta_for_s3(postgres_service_url, s3_client, tmp_file)

    up_url = await dsm.upload_link(fmd.user_id, fmd.file_uuid)
    with io.open(tmp_file, 'rb') as fp:
        d = fp.read()
        req = urllib.request.Request(up_url, data=d, method='PUT')
        with urllib.request.urlopen(req) as _f:
            pass

    #now copy to datcore
    dat_core_uuid = os.path.join(datcore_testbucket, fmd.file_name)

    await dsm.copy_file(user_id=user_id, dest_location=DATCORE_STR, dest_uuid=dat_core_uuid, source_location=SIMCORE_S3_STR,
        source_uuid=fmd.file_uuid)

    data = await dsm.list_files(user_id=user_id, location=DATCORE_STR)

    # there should now be 3 files
    assert len(data) == 3

def test_fmd_build():
    file_uuid = str(Path("1234") / Path("abcd") / Path("xx.dat"))
    fmd = FileMetaData()
    fmd.simcore_from_uuid(file_uuid, "test-bucket")

    assert fmd.node_id == "abcd"
    assert fmd.project_id == "1234"
    assert fmd.file_name == "xx.dat"
    assert fmd.object_name == "1234/abcd/xx.dat"
    assert fmd.file_uuid == file_uuid
    assert fmd.location == SIMCORE_S3_STR
    assert fmd.location_id == SIMCORE_S3_ID
    assert fmd.bucket_name == "test-bucket"
