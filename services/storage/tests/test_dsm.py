# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint:disable=no-name-in-module
# pylint:disable=no-member

import copy
import datetime
import filecmp
import io
import json
import os
import urllib
import uuid
from asyncio import Future
from pathlib import Path
from pprint import pprint
from shutil import copyfile

import attr
import pytest

import utils
from simcore_service_storage.dsm import DataStorageManager
from simcore_service_storage.models import FileMetaData, FileMetaDataEx
from simcore_service_storage.settings import (DATCORE_STR, SIMCORE_S3_ID,
                                              SIMCORE_S3_STR)
from utils import BUCKET_NAME, USER_ID, has_datcore_tokens


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
            for dx in data:
                d = dx.fmd
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
    data1 = await dsm.list_files(user_id=bob_id, location=SIMCORE_S3_STR, regex="astronomy")
    data = data + data1
    bobs_biostromy_files = []
    for d in dsm_mockup_db.keys():
        md = dsm_mockup_db[d]
        if md.user_id == bob_id and (md.project_name == "biology" or md.project_name == "astronomy"):
            bobs_biostromy_files.append(md)

    assert len(data) == len(bobs_biostromy_files)


    # among bobs bio files, filter by project/node, take first one

    uuid_filter = os.path.join(bobs_biostromy_files[0].project_id, bobs_biostromy_files[0].node_id)
    filtered_data = await dsm.list_files(user_id=bob_id, location=SIMCORE_S3_STR, uuid_filter=str(uuid_filter))
    assert filtered_data[0].fmd == bobs_biostromy_files[0]

    for dx in data:
        d = dx.fmd
        await dsm.delete_file(user_id=d.user_id, location=SIMCORE_S3_STR, file_uuid=d.file_uuid)

    # now we should have less items
    new_size = 0
    for _id in id_file_count:
        data = await dsm.list_files(user_id=_id, location=SIMCORE_S3_STR)
        new_size = new_size + len(data)

    assert len(dsm_mockup_db) == new_size + len(bobs_biostromy_files)
    assert len(dsm_mockup_db) == new_size + len(bobs_biostromy_files)


def _create_file_meta_for_s3(postgres_url, s3_client, tmp_file):
    utils.create_tables(url=postgres_url)
    bucket_name = BUCKET_NAME
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)


    # create file and upload
    filename = os.path.basename(tmp_file)
    project_id = "22"
    project_name = "battlestar"
    node_name = "galactica"
    node_id = "1006"
    file_name = filename
    file_uuid = os.path.join(str(project_id), str(node_id), str(file_name))
    display_name = os.path.join(str(project_name), str(node_name), str(file_name))
    created_at = str(datetime.datetime.now())
    file_size = 1234

    d = {   'object_name' : os.path.join(str(project_id), str(node_id), str(file_name)),
            'bucket_name' : bucket_name,
            'file_name' : filename,
            'user_id' : USER_ID,
            'user_name' : "starbucks",
            'location' : SIMCORE_S3_STR,
            'location_id' : SIMCORE_S3_ID,
            'project_id' : project_id,
            'project_name' : project_name,
            'node_id' : node_id,
            'node_name' : node_name,
            'file_uuid' : file_uuid,
            'file_id' : file_uuid,
            'raw_file_path' : file_uuid,
            'display_file_path' : display_name,
            'created_at' : created_at,
            'last_modified' : created_at,
            'file_size' : file_size
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
    down_url = await dsm.download_link_s3(fmd.file_uuid)

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
def test_datcore_fixture(datcore_structured_testbucket):
    if not has_datcore_tokens():
        return
    print(datcore_structured_testbucket)

async def test_dsm_datcore(postgres_service_url, dsm_fixture, datcore_structured_testbucket):
    if not has_datcore_tokens():
        return

    utils.create_tables(url=postgres_service_url)
    dsm = dsm_fixture
    user_id = "0"
    data = await dsm.list_files(user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME)
    # the fixture creates two files
    assert len(data) == 3

    # delete the first one
    fmd_to_delete = data[0].fmd
    print("Deleting", fmd_to_delete.bucket_name, fmd_to_delete.object_name)
    await dsm.delete_file(user_id, DATCORE_STR, fmd_to_delete.file_id)

    data = await dsm.list_files(user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME)
    assert len(data) == 2

async def test_dsm_s3_to_datcore(postgres_service_url, s3_client, mock_files_factory, dsm_fixture, datcore_structured_testbucket):
    if not has_datcore_tokens():
        return
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
    user_id = USER_ID
    down_url = await dsm.download_link_s3(fmd.file_uuid)
    urllib.request.urlretrieve(down_url, tmp_file2)
    assert filecmp.cmp(tmp_file2, tmp_file)
    # now we have the file locally, upload the file
    await dsm.upload_file_to_datcore(user_id=user_id, local_file_path=tmp_file2, destination_id=datcore_structured_testbucket['dataset_id'])
    # and into a deeper strucutre
    await dsm.upload_file_to_datcore(user_id=user_id, local_file_path=tmp_file2, destination_id=datcore_structured_testbucket['coll2_id'])

    data = await dsm.list_files(user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME)
    # there should now be 5 files
    assert len(data) == 5

async def test_dsm_datcore_to_local(postgres_service_url, dsm_fixture, mock_files_factory, datcore_structured_testbucket):
    if not has_datcore_tokens():
        return
    utils.create_tables(url=postgres_service_url)
    dsm = dsm_fixture
    user_id = USER_ID
    data = await dsm.list_files(user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME)
    assert len(data)

    url, filename = await dsm.download_link_datcore(user_id, datcore_structured_testbucket['file_id1'])

    tmp_file = mock_files_factory(1)[0]
    tmp_file2 = tmp_file + ".fromdatcore"

    urllib.request.urlretrieve(url, tmp_file2)

    assert filecmp.cmp(tmp_file2, tmp_file)

async def test_dsm_datcore_to_S3(postgres_service_url, s3_client, dsm_fixture, mock_files_factory, datcore_structured_testbucket):
    if not has_datcore_tokens():
        return
    utils.create_tables(url=postgres_service_url)
    # create temporary file
    tmp_file = mock_files_factory(1)[0]
    dest_fmd = _create_file_meta_for_s3(postgres_service_url, s3_client, tmp_file)
    user_id = dest_fmd.user_id
    dest_uuid = dest_fmd.file_uuid

    dsm = dsm_fixture

    s3_data = await dsm.list_files(user_id=user_id, location=SIMCORE_S3_STR)
    assert len(s3_data) == 0

    dc_data = await dsm.list_files(user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME)
    assert len(dc_data) == 3
    src_fmd = dc_data[0]

    await dsm.copy_file(user_id=user_id, dest_location=SIMCORE_S3_STR, dest_uuid=dest_uuid, source_location=DATCORE_STR,
        source_uuid=datcore_structured_testbucket["file_id1"])

    s3_data = await dsm.list_files(user_id=user_id, location=SIMCORE_S3_STR)
    assert len(s3_data) == 1

    # now download the original file
    tmp_file1 = tmp_file + ".fromdatcore"
    down_url_dc, filename = await dsm.download_link_datcore(user_id, datcore_structured_testbucket["file_id1"])
    urllib.request.urlretrieve(down_url_dc, tmp_file1)

    # and the one on s3
    tmp_file2 = tmp_file + ".fromS3"
    down_url_s3 = await dsm.download_link_s3(dest_uuid)
    urllib.request.urlretrieve(down_url_s3, tmp_file2)

    assert filecmp.cmp(tmp_file1, tmp_file2)

async def test_copy_datcore(postgres_service_url, s3_client, dsm_fixture, mock_files_factory, datcore_structured_testbucket):
    if not has_datcore_tokens():
        return
    utils.create_tables(url=postgres_service_url)

    # the fixture should provide 3 files
    dsm = dsm_fixture
    user_id = USER_ID
    data = await dsm.list_files(user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME)
    assert len(data) == 3

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
    dat_core_uuid = os.path.join(BUCKET_NAME, fmd.file_name)

    await dsm.copy_file(user_id=user_id, dest_location=DATCORE_STR, dest_uuid=datcore_structured_testbucket["coll2_id"], source_location=SIMCORE_S3_STR,
        source_uuid=fmd.file_uuid)

    data = await dsm.list_files(user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME)

    # there should now be 4 files
    assert len(data) == 4

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


async def test_dsm_complete_db(dsm_fixture, dsm_mockup_complete_db):
    dsm = dsm_fixture
    _id = "21"
    dsm.has_project_db = True
    data = await dsm.list_files(user_id=_id, location=SIMCORE_S3_STR)

    assert len(data) == 2
    for dx in data:
        d = dx.fmd
        assert d.display_file_path
        assert d.node_name
        assert d.project_name
        assert d.raw_file_path


async def test_delete_data_folders(dsm_fixture, dsm_mockup_complete_db):
    file_1, file_2 = dsm_mockup_complete_db
    _id = "21"
    data = await dsm_fixture.list_files(user_id=_id, location=SIMCORE_S3_STR)
    response = await dsm_fixture.delete_project_simcore_s3(user_id=_id, project_id=file_1["project_id"], node_id=file_1["node_id"])
    data = await dsm_fixture.list_files(user_id=_id, location=SIMCORE_S3_STR)
    assert len(data) == 1
    assert data[0].fmd.file_name == file_2["filename"]
    response = await dsm_fixture.delete_project_simcore_s3(user_id=_id, project_id=file_1["project_id"], node_id=None)
    data = await dsm_fixture.list_files(user_id=_id, location=SIMCORE_S3_STR)
    assert not data


async def test_deep_copy_project_simcore_s3(dsm_fixture, s3_client, postgres_service_url, datcore_structured_testbucket):
    if not has_datcore_tokens():
        return
    dsm = dsm_fixture
    utils.create_full_tables(url=postgres_service_url)

    path_in_datcore = datcore_structured_testbucket["file_id3"]
    file_name_in_datcore = Path(datcore_structured_testbucket["filename3"]).name
    user_id = USER_ID

    source_project =  {
        "uuid": "template-uuid-4d5e-b80e-401c8066782f",
        "name": "ISAN: 2D Plot",
        "description": "2D RawGraphs viewer with one input",
        "thumbnail": "",
        "prjOwner": "maiz",
        "creationDate": "2019-05-24T10:36:57.813Z",
        "lastChangeDate": "2019-05-24T11:36:12.015Z",
        "workbench": {
          "template-uuid-48eb-a9d2-aaad6b72400a": {
            "key": "simcore/services/frontend/file-picker",
            "version": "1.0.0",
            "label": "File Picker",
            "inputs": {},
            "inputNodes": [],
            "outputNode": False,
            "outputs": {
              "outFile": {
                "store": 1,
                "path": "N:package:ab8c214d-a596-401f-a90c-9c50e3c048b0"
              }
            },
            "progress": 100,
            "thumbnail": "",
            "position": {
              "x": 100,
              "y": 100
            }
          },
          "template-uuid-4c63-a705-03a2c339646c": {
            "key": "simcore/services/dynamic/raw-graphs",
            "version": "2.8.0",
            "label": "2D plot",
            "inputs": {
              "input_1": {
                "nodeUuid": "template-uuid-48eb-a9d2-aaad6b72400a",
                "output": "outFile"
              }
            },
            "inputNodes": [
              "template-uuid-48eb-a9d2-aaad6b72400a"
            ],
            "outputNode": False,
            "outputs": {},
            "progress": 0,
            "thumbnail": "",
            "position": {
              "x": 400,
              "y": 100
            }
          }
        }
    }

    bucket_name = BUCKET_NAME
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)

    source_project["workbench"]["template-uuid-48eb-a9d2-aaad6b72400a"]["outputs"]["outFile"]["path"] = path_in_datcore

    destination_project = copy.deepcopy(source_project)
    source_project_id = source_project["uuid"]
    destination_project["uuid"] = source_project_id.replace("template", "deep-copy")
    destination_project["workbench"] = {}

    node_mapping = {}

    for node_id, node in source_project["workbench"].items():
        object_name = str(Path(source_project_id) / Path(node_id) / Path(node_id + ".dat"))
        f = utils.data_dir() / Path("notebooks.zip")
        s3_client.upload_file(bucket_name, object_name, f)
        key = node_id.replace("template", "deep-copy")
        destination_project["workbench"][key] = node
        node_mapping[node_id] = key

    status = await dsm.deep_copy_project_simcore_s3(user_id, source_project, destination_project, node_mapping)

    new_path = destination_project["workbench"]["deep-copy-uuid-48eb-a9d2-aaad6b72400a"]["outputs"]["outFile"]["path"]
    assert new_path != path_in_datcore
    assert Path(new_path).name == file_name_in_datcore
    files = await dsm.list_files(user_id=user_id, location=SIMCORE_S3_STR)
    assert len(files) == 3
    # one of the files in s3 should be the dowloaded one from datcore
    assert any(f.fmd.file_name == Path(datcore_structured_testbucket["filename3"]).name for f in files)

    response = await dsm.delete_project_simcore_s3(user_id, destination_project["uuid"])

    files = await dsm.list_files(user_id=user_id, location=SIMCORE_S3_STR)
    assert len(files) == 0

async def test_dsm_list_datasets_s3(dsm_fixture, dsm_mockup_complete_db):
    dsm_fixture.has_project_db = True

    datasets = await dsm_fixture.list_datasets(user_id="21", location=SIMCORE_S3_STR)

    assert len(datasets) == 2
    assert any("Kember" in d.display_name for d in datasets)

async def test_dsm_list_datasets_datcore(dsm_fixture, datcore_structured_testbucket):
    if not has_datcore_tokens():
        return

    datasets = await dsm_fixture.list_datasets(user_id=USER_ID, location=DATCORE_STR)

    assert len(datasets)
    assert any(BUCKET_NAME in d.display_name for d in datasets)

async def test_dsm_list_dataset_files_s3(dsm_fixture, dsm_mockup_complete_db):
    dsm_fixture.has_project_db = True

    datasets = await dsm_fixture.list_datasets(user_id="21", location=SIMCORE_S3_STR)
    assert len(datasets) == 2
    assert any("Kember" in d.display_name for d in datasets)
    for d in datasets:
        files = await dsm_fixture.list_files_dataset(user_id="21", location=SIMCORE_S3_STR, dataset_id=d.dataset_id)
        if "Kember" in d.display_name:
            assert len(files) == 2
        else:
            assert len(files) == 0

async def test_dsm_list_dataset_files_datcore(dsm_fixture, datcore_structured_testbucket):
    if not has_datcore_tokens():
        return

    datasets = await dsm_fixture.list_datasets(user_id=USER_ID, location=DATCORE_STR)

    assert len(datasets)
    assert any(BUCKET_NAME in d.display_name for d in datasets)

    for d in datasets:
        files = await dsm_fixture.list_files_dataset(user_id=USER_ID, location=DATCORE_STR, dataset_id=d.dataset_id)
        if BUCKET_NAME in d.display_name:
            assert len(files) == 3

@pytest.mark.skip(reason="develop only")
async def test_download_links(datcore_structured_testbucket, s3_client, mock_files_factory):
    s3_client.create_bucket(BUCKET_NAME, delete_contents_if_exists=True)
    _file = mock_files_factory(count=1)[0]

    s3_client.upload_file(BUCKET_NAME, "test.txt", _file)
    link = s3_client.create_presigned_get_url(BUCKET_NAME, "test.txt")
    print(link)

    dcw = datcore_structured_testbucket['dcw']

    endings = ['txt', 'json', 'zip', 'dat', 'mat']
    counter = 1
    for e in endings:
        file_name = "test{}.{}".format(counter, e)
        file2 = str(Path(_file).parent / file_name)
        copyfile(_file, file_name)
        dataset_id = datcore_structured_testbucket['dataset_id']
        file_id = await dcw.upload_file_to_id(dataset_id, file_name)
        link, _file_name = await dcw.download_link_by_id(file_id)
        print(_file_name, link)
        os.remove(file_name)
