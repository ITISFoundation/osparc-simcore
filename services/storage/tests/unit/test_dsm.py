# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=no-name-in-module
# pylint: disable=no-member
# pylint: disable=too-many-branches

import copy
import datetime
import filecmp
import os
import urllib.request
import uuid
from pathlib import Path
from shutil import copyfile
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import pytest
import tests.utils
from simcore_service_storage.access_layer import InvalidFileIdentifier
from simcore_service_storage.constants import DATCORE_STR, SIMCORE_S3_ID, SIMCORE_S3_STR
from simcore_service_storage.dsm import DataStorageManager
from simcore_service_storage.models import FileMetaData, FileMetaDataEx
from simcore_service_storage.s3wrapper.s3_client import MinioClientWrapper
from tests.utils import BUCKET_NAME, USER_ID, has_datcore_tokens

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["minio", "adminer"]


async def test_dsm_s3(
    dsm_mockup_db: Dict[str, FileMetaData], dsm_fixture: DataStorageManager
):
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

    # list files for every user
    for _id in id_file_count:
        data = await dsm.list_files(user_id=_id, location=SIMCORE_S3_STR)
        assert len(data) == id_file_count[_id]

    # Get files from bob from the project biology
    bob_id = 0
    for _id, _name in id_name_map.items():
        if _name == "bob":
            bob_id = _id
            break
    assert not bob_id == 0

    data = await dsm.list_files(
        user_id=bob_id, location=SIMCORE_S3_STR, regex="biology"
    )
    data1 = await dsm.list_files(
        user_id=bob_id, location=SIMCORE_S3_STR, regex="astronomy"
    )
    data = data + data1
    bobs_biostromy_files = []
    for d in dsm_mockup_db.keys():
        md = dsm_mockup_db[d]
        if md.user_id == bob_id and (md.project_name in ("biology", "astronomy")):
            bobs_biostromy_files.append(md)

    assert len(data) == len(bobs_biostromy_files)

    # among bobs bio files, filter by project/node, take first one

    uuid_filter = os.path.join(
        bobs_biostromy_files[0].project_id, bobs_biostromy_files[0].node_id
    )
    filtered_data = await dsm.list_files(
        user_id=bob_id, location=SIMCORE_S3_STR, uuid_filter=str(uuid_filter)
    )
    assert filtered_data[0].fmd == bobs_biostromy_files[0]

    for dx in data:
        d = dx.fmd
        await dsm.delete_file(
            user_id=d.user_id, location=SIMCORE_S3_STR, file_uuid=d.file_uuid
        )

    # now we should have less items
    new_size = 0
    for _id in id_file_count:
        data = await dsm.list_files(user_id=_id, location=SIMCORE_S3_STR)
        new_size = new_size + len(data)

    assert len(dsm_mockup_db) == new_size + len(bobs_biostromy_files)
    assert len(dsm_mockup_db) == new_size + len(bobs_biostromy_files)


@pytest.fixture
def create_file_meta_for_s3(
    s3_client: MinioClientWrapper,
    cleanup_user_projects_file_metadata: None,
) -> Iterator[Callable[..., FileMetaData]]:
    def _creator(tmp_file: Path) -> FileMetaData:
        bucket_name = BUCKET_NAME
        s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)

        # create file and upload
        filename = tmp_file.name
        project_id = "api"  # "357879cc-f65d-48b2-ad6c-074e2b9aa1c7"
        project_name = "battlestar"
        node_name = "galactica"
        node_id = "b423b654-686d-4157-b74b-08fa9d90b36e"
        file_name = filename
        file_uuid = os.path.join(str(project_id), str(node_id), str(file_name))
        display_name = os.path.join(str(project_name), str(node_name), str(file_name))
        created_at = str(datetime.datetime.now())
        file_size = tmp_file.stat().st_size

        d = {
            "object_name": os.path.join(str(project_id), str(node_id), str(file_name)),
            "bucket_name": bucket_name,
            "file_name": filename,
            "user_id": USER_ID,
            "user_name": "starbucks",
            "location": SIMCORE_S3_STR,
            "location_id": SIMCORE_S3_ID,
            "project_id": project_id,
            "project_name": project_name,
            "node_id": node_id,
            "node_name": node_name,
            "file_uuid": file_uuid,
            "file_id": file_uuid,
            "raw_file_path": file_uuid,
            "display_file_path": display_name,
            "created_at": created_at,
            "last_modified": created_at,
            "file_size": file_size,
        }

        fmd = FileMetaData(**d)

        return fmd

    yield _creator

    # cleanup
    s3_client.remove_bucket(BUCKET_NAME, delete_contents=True)


async def _upload_file(
    dsm: DataStorageManager, file_metadata: FileMetaData, file_path: Path
) -> FileMetaData:
    up_url = await dsm.upload_link(
        file_metadata.user_id, file_metadata.file_uuid, as_presigned_link=True
    )
    assert file_path.exists()
    with file_path.open("rb") as fp:
        d = fp.read()
        req = urllib.request.Request(up_url, data=d, method="PUT")
        with urllib.request.urlopen(req) as _f:
            entity_tag = _f.headers.get("ETag")
    assert entity_tag is not None
    file_metadata.entity_tag = entity_tag.strip('"')
    return file_metadata


async def test_update_metadata_from_storage(
    postgres_dsn_url: str,
    s3_client: MinioClientWrapper,
    mock_files_factory: Callable[[int], List[Path]],
    dsm_fixture: DataStorageManager,
    create_file_meta_for_s3: Callable,
):
    tmp_file = mock_files_factory(1)[0]
    fmd: FileMetaData = create_file_meta_for_s3(tmp_file)
    fmd = await _upload_file(dsm_fixture, fmd, Path(tmp_file))

    assert (
        await dsm_fixture.try_update_database_from_storage(  # pylint: disable=protected-access
            "some_fake_uuid", fmd.bucket_name, fmd.object_name
        )
        is None
    )

    assert (
        await dsm_fixture.try_update_database_from_storage(  # pylint: disable=protected-access
            fmd.file_uuid, "some_fake_bucket", fmd.object_name
        )
        is None
    )

    assert (
        await dsm_fixture.try_update_database_from_storage(  # pylint: disable=protected-access
            fmd.file_uuid, fmd.bucket_name, "some_fake_object"
        )
        is None
    )

    file_metadata: Optional[
        FileMetaDataEx
    ] = await dsm_fixture.try_update_database_from_storage(  # pylint: disable=protected-access
        fmd.file_uuid, fmd.bucket_name, fmd.object_name
    )
    assert file_metadata is not None
    assert file_metadata.fmd.file_size == Path(tmp_file).stat().st_size
    assert file_metadata.fmd.entity_tag == fmd.entity_tag


async def test_links_s3(
    postgres_dsn_url: str,
    s3_client: MinioClientWrapper,
    mock_files_factory: Callable[[int], List[Path]],
    dsm_fixture: DataStorageManager,
    create_file_meta_for_s3: Callable,
):

    tmp_file = mock_files_factory(1)[0]
    fmd: FileMetaData = create_file_meta_for_s3(tmp_file)

    dsm = dsm_fixture

    fmd = await _upload_file(dsm_fixture, fmd, Path(tmp_file))

    # test wrong user
    assert await dsm.list_file("654654654", fmd.location, fmd.file_uuid) is None

    # test wrong location
    assert await dsm.list_file(fmd.user_id, "whatever_location", fmd.file_uuid) is None

    # test wrong file uuid
    with pytest.raises(InvalidFileIdentifier):
        await dsm.list_file(fmd.user_id, fmd.location, "some_fake_uuid")
    # use correctly
    file_metadata: Optional[FileMetaDataEx] = await dsm.list_file(
        fmd.user_id, fmd.location, fmd.file_uuid
    )
    assert file_metadata is not None
    excluded_fields = [
        "project_id",
        "project_name",
        "node_name",
        "user_name",
        "display_file_path",
        "created_at",
        "last_modified",
    ]
    for field in FileMetaData.__attrs_attrs__:
        if field.name not in excluded_fields:
            if field.name == "location_id":
                assert int(
                    file_metadata.fmd.__getattribute__(field.name)
                ) == fmd.__getattribute__(
                    field.name
                ), f"{field.name}: expected {fmd.__getattribute__(field.name)} vs {file_metadata.fmd.__getattribute__(field.name)}"
            else:
                assert file_metadata.fmd.__getattribute__(
                    field.name
                ) == fmd.__getattribute__(
                    field.name
                ), f"{field.name}: expected {fmd.__getattribute__(field.name)} vs {file_metadata.fmd.__getattribute__(field.name)}"

    tmp_file2 = f"{tmp_file}.rec"
    user_id = 0
    down_url = await dsm.download_link_s3(
        fmd.file_uuid, user_id, as_presigned_link=True
    )

    urllib.request.urlretrieve(down_url, tmp_file2)

    assert filecmp.cmp(tmp_file2, tmp_file)


async def test_copy_s3_s3(
    postgres_dsn_url: str,
    s3_client: MinioClientWrapper,
    mock_files_factory: Callable[[int], List[Path]],
    dsm_fixture: DataStorageManager,
    create_file_meta_for_s3: Callable,
):

    tmp_file = mock_files_factory(1)[0]
    fmd = create_file_meta_for_s3(tmp_file)

    dsm = dsm_fixture
    data = await dsm.list_files(user_id=fmd.user_id, location=SIMCORE_S3_STR)
    assert len(data) == 0

    # upload the file
    up_url = await dsm.upload_link(fmd.user_id, fmd.file_uuid, as_presigned_link=True)
    with tmp_file.open("rb") as fp:
        d = fp.read()
        req = urllib.request.Request(up_url, data=d, method="PUT")
        with urllib.request.urlopen(req) as _f:
            pass

    data = await dsm.list_files(user_id=fmd.user_id, location=SIMCORE_S3_STR)
    assert len(data) == 1

    from_uuid = fmd.file_uuid
    new_project = "zoology"
    to_uuid = os.path.join(new_project, fmd.node_id, fmd.file_name)
    await dsm.copy_file(
        user_id=fmd.user_id,
        dest_location=SIMCORE_S3_STR,
        dest_uuid=to_uuid,
        source_location=SIMCORE_S3_STR,
        source_uuid=from_uuid,
    )

    data = await dsm.list_files(user_id=fmd.user_id, location=SIMCORE_S3_STR)

    assert len(data) == 2


# NOTE: Below tests directly access the datcore platform, use with care!
@pytest.mark.skipif(not has_datcore_tokens(), reason="no datcore tokens")
def test_datcore_fixture(datcore_structured_testbucket):
    print(datcore_structured_testbucket)


@pytest.mark.skipif(not has_datcore_tokens(), reason="no datcore tokens")
async def test_dsm_datcore(
    postgres_dsn_url, dsm_fixture, datcore_structured_testbucket
):
    dsm = dsm_fixture
    user_id = "0"
    data = await dsm.list_files(
        user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME
    )
    # the fixture creates 3 files
    assert len(data) == 3

    # delete the first one
    fmd_to_delete = data[0].fmd
    print("Deleting", fmd_to_delete.bucket_name, fmd_to_delete.object_name)
    is_deleted = await dsm.delete_file(user_id, DATCORE_STR, fmd_to_delete.file_id)
    assert is_deleted

    import time

    time.sleep(1)  # FIXME: takes some time to delete!!

    data = await dsm.list_files(
        user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME
    )
    assert len(data) == 2


@pytest.mark.skipif(not has_datcore_tokens(), reason="no datcore tokens")
async def test_dsm_s3_to_datcore(
    postgres_dsn_url: str,
    s3_client: MinioClientWrapper,
    mock_files_factory: Callable[[int], List[Path]],
    dsm_fixture: DataStorageManager,
    datcore_structured_testbucket: str,
    create_file_meta_for_s3: Callable,
):
    tmp_file = mock_files_factory(1)[0]

    fmd = create_file_meta_for_s3(tmp_file)

    dsm = dsm_fixture

    up_url = await dsm.upload_link(fmd.user_id, fmd.file_uuid, as_presigned_link=True)
    with tmp_file.open("rb") as fp:
        d = fp.read()
        req = urllib.request.Request(up_url, data=d, method="PUT")
        with urllib.request.urlopen(req) as _f:
            pass

    # given the fmd, upload to datcore
    tmp_file2 = f"{tmp_file}.fordatcore"
    user_id = USER_ID
    down_url = await dsm.download_link_s3(
        fmd.file_uuid, user_id, as_presigned_link=True
    )
    urllib.request.urlretrieve(down_url, tmp_file2)
    assert filecmp.cmp(tmp_file2, tmp_file)
    # now we have the file locally, upload the file
    await dsm.upload_file_to_datcore(
        user_id,
        tmp_file2,
        datcore_structured_testbucket["dataset_id"],
    )
    # and into a deeper strucutre
    await dsm.upload_file_to_datcore(
        user_id,
        tmp_file2,
        datcore_structured_testbucket["coll2_id"],
    )

    # FIXME: upload takes some time
    import time

    time.sleep(1)

    data = await dsm.list_files(
        user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME
    )
    # there should now be 5 files
    assert len(data) == 5


@pytest.mark.skipif(not has_datcore_tokens(), reason="no datcore tokens")
async def test_dsm_datcore_to_local(
    postgres_dsn_url,
    dsm_fixture: DataStorageManager,
    mock_files_factory: Callable[[int], List[Path]],
    datcore_structured_testbucket,
):

    dsm = dsm_fixture
    user_id = USER_ID
    data = await dsm.list_files(
        user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME
    )
    assert len(data)

    url, filename = await dsm.download_link_datcore(
        user_id, datcore_structured_testbucket["file_id1"]
    )

    tmp_file = mock_files_factory(1)[0]
    tmp_file2 = f"{tmp_file}.fromdatcore"

    urllib.request.urlretrieve(url, tmp_file2)

    assert filecmp.cmp(tmp_file2, tmp_file)


@pytest.mark.skipif(not has_datcore_tokens(), reason="no datcore tokens")
async def test_dsm_datcore_to_S3(
    postgres_dsn_url: str,
    s3_client: MinioClientWrapper,
    dsm_fixture: DataStorageManager,
    mock_files_factory: Callable[[int], List[Path]],
    datcore_structured_testbucket: str,
    create_file_meta_for_s3: Callable,
):
    # create temporary file
    tmp_file = mock_files_factory(1)[0]
    dest_fmd = create_file_meta_for_s3(tmp_file)
    user_id = dest_fmd.user_id
    dest_uuid = dest_fmd.file_uuid

    dsm = dsm_fixture

    s3_data = await dsm.list_files(user_id=user_id, location=SIMCORE_S3_STR)
    assert len(s3_data) == 0

    dc_data = await dsm.list_files(
        user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME
    )
    assert len(dc_data) == 3
    src_fmd = dc_data[0]

    await dsm.copy_file(
        user_id=user_id,
        dest_location=SIMCORE_S3_STR,
        dest_uuid=dest_uuid,
        source_location=DATCORE_STR,
        source_uuid=datcore_structured_testbucket["file_id1"],
    )

    s3_data = await dsm.list_files(user_id=user_id, location=SIMCORE_S3_STR)
    assert len(s3_data) == 1

    # now download the original file
    tmp_file1 = f"{tmp_file}.fromdatcore"
    down_url_dc, filename = await dsm.download_link_datcore(
        user_id, datcore_structured_testbucket["file_id1"]
    )
    urllib.request.urlretrieve(down_url_dc, tmp_file1)

    # and the one on s3
    tmp_file2 = f"{tmp_file}.fromS3"
    down_url_s3 = await dsm.download_link_s3(dest_uuid, user_id, as_presigned_link=True)
    urllib.request.urlretrieve(down_url_s3, tmp_file2)

    assert filecmp.cmp(tmp_file1, tmp_file2)


@pytest.mark.skipif(not has_datcore_tokens(), reason="no datcore tokens")
async def test_copy_datcore(
    postgres_dsn_url: str,
    s3_client: MinioClientWrapper,
    dsm_fixture: DataStorageManager,
    mock_files_factory: Callable[[int], List[Path]],
    datcore_structured_testbucket: str,
    create_file_meta_for_s3: Callable,
):
    # the fixture should provide 3 files
    dsm = dsm_fixture
    user_id = USER_ID
    data = await dsm.list_files(
        user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME
    )
    assert len(data) == 3

    # create temporary file and upload to s3
    tmp_file = mock_files_factory(1)[0]
    fmd = create_file_meta_for_s3(tmp_file)

    up_url = await dsm.upload_link(fmd.user_id, fmd.file_uuid, as_presigned_link=True)
    with tmp_file.open("rb") as fp:
        d = fp.read()
        req = urllib.request.Request(up_url, data=d, method="PUT")
        with urllib.request.urlopen(req) as _f:
            pass

    # now copy to datcore
    dat_core_uuid = os.path.join(BUCKET_NAME, fmd.file_name)

    await dsm.copy_file(
        user_id=user_id,
        dest_location=DATCORE_STR,
        dest_uuid=datcore_structured_testbucket["coll2_id"],
        source_location=SIMCORE_S3_STR,
        source_uuid=fmd.file_uuid,
    )

    data = await dsm.list_files(
        user_id=user_id, location=DATCORE_STR, uuid_filter=BUCKET_NAME
    )

    # there should now be 4 files
    assert len(data) == 4


def test_fmd_build():
    file_uuid = str(Path("api") / Path("abcd") / Path("xx.dat"))
    fmd = FileMetaData()
    fmd.simcore_from_uuid(file_uuid, "test-bucket")

    assert not fmd.node_id
    assert not fmd.project_id
    assert fmd.file_name == "xx.dat"
    assert fmd.object_name == "api/abcd/xx.dat"
    assert fmd.file_uuid == file_uuid
    assert fmd.location == SIMCORE_S3_STR
    assert fmd.location_id == SIMCORE_S3_ID
    assert fmd.bucket_name == "test-bucket"

    file_uuid = f"{uuid.uuid4()}/{uuid.uuid4()}/xx.dat"
    fmd.simcore_from_uuid(file_uuid, "test-bucket")

    assert fmd.node_id == file_uuid.split("/")[1]
    assert fmd.project_id == file_uuid.split("/")[0]
    assert fmd.file_name == "xx.dat"
    assert fmd.object_name == file_uuid
    assert fmd.file_uuid == file_uuid
    assert fmd.location == SIMCORE_S3_STR
    assert fmd.location_id == SIMCORE_S3_ID
    assert fmd.bucket_name == "test-bucket"


async def test_dsm_complete_db(
    dsm_fixture: DataStorageManager,
    dsm_mockup_complete_db: Tuple[Dict[str, str], Dict[str, str]],
):
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


async def test_delete_data_folders(
    dsm_fixture: DataStorageManager,
    dsm_mockup_complete_db: Tuple[Dict[str, str], Dict[str, str]],
):
    file_1, file_2 = dsm_mockup_complete_db
    _id = "21"
    data = await dsm_fixture.list_files(user_id=_id, location=SIMCORE_S3_STR)
    response = await dsm_fixture.delete_project_simcore_s3(
        user_id=_id, project_id=file_1["project_id"], node_id=file_1["node_id"]
    )
    data = await dsm_fixture.list_files(user_id=_id, location=SIMCORE_S3_STR)
    assert len(data) == 1
    assert data[0].fmd.file_name == file_2["filename"]
    response = await dsm_fixture.delete_project_simcore_s3(
        user_id=_id, project_id=file_1["project_id"], node_id=None
    )
    data = await dsm_fixture.list_files(user_id=_id, location=SIMCORE_S3_STR)
    assert not data


@pytest.mark.skipif(not has_datcore_tokens(), reason="no datcore tokens")
async def test_deep_copy_project_simcore_s3(
    dsm_fixture, s3_client, postgres_dsn_url, datcore_structured_testbucket
):
    dsm = dsm_fixture

    tests.utils.fill_tables_from_csv_files(url=postgres_dsn_url)

    path_in_datcore = datcore_structured_testbucket["file_id3"]
    file_name_in_datcore = Path(datcore_structured_testbucket["filename3"]).name
    user_id = USER_ID

    source_project = {
        "uuid": "de2578c5-431e-4d5e-b80e-401c8066782f",
        "name": "ISAN: 2D Plot",
        "description": "2D RawGraphs viewer with one input",
        "thumbnail": "",
        "prjOwner": "my.email@osparc.io",
        "creationDate": "2019-05-24T10:36:57.813Z",
        "lastChangeDate": "2019-05-24T11:36:12.015Z",
        "workbench": {
            "de2578c5-431e-48eb-a9d2-aaad6b72400a": {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "File Picker",
                "inputs": {},
                "inputNodes": [],
                "outputs": {
                    "outFile": {
                        "store": 1,
                        "path": "N:package:ab8c214d-a596-401f-a90c-9c50e3c048b0",
                    }
                },
                "progress": 100,
                "thumbnail": "",
                "position": {"x": 100, "y": 100},
            },
            "de2578c5-431e-4c63-a705-03a2c339646c": {
                "key": "simcore/services/dynamic/raw-graphs",
                "version": "2.8.0",
                "label": "2D plot",
                "inputs": {
                    "input_1": {
                        "nodeUuid": "de2578c5-431e-48eb-a9d2-aaad6b72400a",
                        "output": "outFile",
                    }
                },
                "inputNodes": ["de2578c5-431e-48eb-a9d2-aaad6b72400a"],
                "outputs": {},
                "progress": 0,
                "thumbnail": "",
                "position": {"x": 400, "y": 100},
            },
        },
    }

    bucket_name = BUCKET_NAME
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)

    source_project["workbench"]["de2578c5-431e-48eb-a9d2-aaad6b72400a"]["outputs"][
        "outFile"
    ]["path"] = path_in_datcore

    destination_project = copy.deepcopy(source_project)
    source_project_id = source_project["uuid"]
    destination_project["uuid"] = source_project_id.replace("template", "deep-copy")
    destination_project["workbench"] = {}

    node_mapping = {}

    for node_id, node in source_project["workbench"].items():
        object_name = str(
            Path(source_project_id) / Path(node_id) / Path(node_id + ".dat")
        )
        f = tests.utils.data_dir() / Path("notebooks.zip")
        s3_client.upload_file(bucket_name, object_name, f)
        key = node_id.replace("template", "deep-copy")
        destination_project["workbench"][key] = node
        node_mapping[node_id] = key

    status = await dsm.deep_copy_project_simcore_s3(
        user_id, source_project, destination_project, node_mapping
    )

    new_path = destination_project["workbench"][
        "deep-copy-uuid-48eb-a9d2-aaad6b72400a"
    ]["outputs"]["outFile"]["path"]
    assert new_path != path_in_datcore
    assert Path(new_path).name == file_name_in_datcore
    files = await dsm.list_files(user_id=user_id, location=SIMCORE_S3_STR)
    assert len(files) == 3
    # one of the files in s3 should be the dowloaded one from datcore
    assert any(
        f.fmd.file_name == Path(datcore_structured_testbucket["filename3"]).name
        for f in files
    )

    response = await dsm.delete_project_simcore_s3(user_id, destination_project["uuid"])

    files = await dsm.list_files(user_id=user_id, location=SIMCORE_S3_STR)
    assert len(files) == 0


async def test_dsm_list_datasets_s3(dsm_fixture, dsm_mockup_complete_db):
    dsm_fixture.has_project_db = True

    datasets = await dsm_fixture.list_datasets(user_id="21", location=SIMCORE_S3_STR)

    assert len(datasets) == 1
    assert any("Kember" in d.display_name for d in datasets)


async def test_sync_table_meta_data(
    dsm_fixture: DataStorageManager,
    dsm_mockup_complete_db: Tuple[Dict[str, str], Dict[str, str]],
    s3_client: MinioClientWrapper,
):
    dsm_fixture.has_project_db = True

    expected_removed_files = []
    # the list should be empty on start
    list_changes: Dict[str, Any] = await dsm_fixture.synchronise_meta_data_table(
        location=SIMCORE_S3_STR, dry_run=True
    )
    assert "removed" in list_changes
    assert list_changes["removed"] == expected_removed_files

    # now remove the files
    for file_entry in dsm_mockup_complete_db:
        s3_key = f"{file_entry['project_id']}/{file_entry['node_id']}/{file_entry['filename']}"
        s3_client.remove_objects(BUCKET_NAME, [s3_key])
        expected_removed_files.append(s3_key)

        # the list should now contain the removed entries
        list_changes: Dict[str, Any] = await dsm_fixture.synchronise_meta_data_table(
            location=SIMCORE_S3_STR, dry_run=True
        )
        assert "removed" in list_changes
        assert list_changes["removed"] == expected_removed_files

    # now effectively call the function should really remove the files
    list_changes: Dict[str, Any] = await dsm_fixture.synchronise_meta_data_table(
        location=SIMCORE_S3_STR, dry_run=False
    )
    # listing again will show an empty list again
    list_changes: Dict[str, Any] = await dsm_fixture.synchronise_meta_data_table(
        location=SIMCORE_S3_STR, dry_run=True
    )
    assert "removed" in list_changes
    assert list_changes["removed"] == []


@pytest.mark.skipif(not has_datcore_tokens(), reason="no datcore tokens")
async def test_dsm_list_datasets_datcore(
    dsm_fixture: DataStorageManager, datcore_structured_testbucket: str
):
    datasets = await dsm_fixture.list_datasets(user_id=USER_ID, location=DATCORE_STR)

    assert len(datasets)
    assert any(BUCKET_NAME in d.display_name for d in datasets)


async def test_dsm_list_dataset_files_s3(
    dsm_fixture: DataStorageManager,
    dsm_mockup_complete_db: Tuple[Dict[str, str], Dict[str, str]],
):
    dsm_fixture.has_project_db = True

    datasets = await dsm_fixture.list_datasets(user_id="21", location=SIMCORE_S3_STR)
    assert len(datasets) == 1
    assert any("Kember" in d.display_name for d in datasets)
    for d in datasets:
        files = await dsm_fixture.list_files_dataset(
            user_id="21", location=SIMCORE_S3_STR, dataset_id=d.dataset_id
        )
        if "Kember" in d.display_name:
            assert len(files) == 2
        else:
            assert len(files) == 0

        if files:
            found = await dsm_fixture.search_files_starting_with(
                user_id="21", prefix=files[0].fmd.file_uuid
            )
            assert found
            assert len(found) == 1
            assert found[0].fmd.file_uuid == files[0].fmd.file_uuid
            assert found[0].parent_id == files[0].parent_id
            assert found[0].fmd.node_id == files[0].fmd.node_id
            # NOTE: found and files differ in these attributes
            #  ['project_name', 'node_name', 'file_id', 'raw_file_path', 'display_file_path']
            #  because these are added artificially in list_files


@pytest.mark.skipif(not has_datcore_tokens(), reason="no datcore tokens")
async def test_dsm_list_dataset_files_datcore(
    dsm_fixture: DataStorageManager, datcore_structured_testbucket: str
):
    datasets = await dsm_fixture.list_datasets(user_id=USER_ID, location=DATCORE_STR)

    assert len(datasets)
    assert any(BUCKET_NAME in d.display_name for d in datasets)

    for d in datasets:
        files = await dsm_fixture.list_files_dataset(
            user_id=USER_ID, location=DATCORE_STR, dataset_id=d.dataset_id
        )
        if BUCKET_NAME in d.display_name:
            assert len(files) == 3


@pytest.mark.skip(reason="develop only")
@pytest.mark.skipif(not has_datcore_tokens(), reason="no datcore tokens")
async def test_download_links(
    datcore_structured_testbucket: str,
    s3_client: MinioClientWrapper,
    mock_files_factory: Callable[[int], List[Path]],
):
    s3_client.create_bucket(BUCKET_NAME, delete_contents_if_exists=True)
    _file = mock_files_factory(1)[0]

    s3_client.upload_file(BUCKET_NAME, "test.txt", f"{_file}")
    link = s3_client.create_presigned_get_url(BUCKET_NAME, "test.txt")
    print(link)

    dcw = datcore_structured_testbucket["dcw"]

    endings = ["txt", "json", "zip", "dat", "mat"]
    counter = 1
    for e in endings:
        file_name = "test{}.{}".format(counter, e)
        copyfile(_file, file_name)
        dataset_id = datcore_structured_testbucket["dataset_id"]
        file_id = await dcw.upload_file_to_id(dataset_id, file_name)
        link, _file_name = await dcw.download_link_by_id(file_id)
        print(_file_name, link)
        os.remove(file_name)
