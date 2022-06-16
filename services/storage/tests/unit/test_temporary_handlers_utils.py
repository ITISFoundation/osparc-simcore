from typing import Any

import pytest
from models_library.api_schemas_storage import DatasetMetaDataGet, FileMetaDataGet
from simcore_service_storage.models import DatasetMetaData, FileMetaData, FileMetaDataEx
from simcore_service_storage.temporary_handlers_utils import (
    convert_to_api_dataset,
    convert_to_api_fmd,
)


@pytest.mark.parametrize(
    "internal_dataset_metadata, expected_dataset_metadata_get",
    [
        (DatasetMetaData(**d), DatasetMetaDataGet.parse_obj(d))
        for d in DatasetMetaDataGet.Config.schema_extra["examples"]
    ],
)
def test_convert_to_api_dataset(
    internal_dataset_metadata: DatasetMetaData,
    expected_dataset_metadata_get: DatasetMetaDataGet,
):
    assert (
        convert_to_api_dataset(internal_dataset_metadata)
        == expected_dataset_metadata_get
    )


_EXAMPLE_OLD_FILEMETADATA_EX = [
    # simcore S3
    {
        "bucket_name": "master-simcore",
        "created_at": "2022-05-30 15:14:00.005624",
        "display_file_path": "New Study (1)/Docker Swarm Services - Grafana.pptx/Docker Swarm Services - Grafana.pptx",
        "entity_tag": "8ee3ebd91fe8b873695defdc609b16f2",
        "file_id": "1b3623fa-e02b-11ec-8777-02420a0194f6/dbc18a00-67bd-4064-92d4-0d696ed1982c/Docker Swarm Services - Grafana.pptx",
        "file_name": "Docker Swarm Services - Grafana.pptx",
        "file_size": 725842,
        "file_uuid": "1b3623fa-e02b-11ec-8777-02420a0194f6/dbc18a00-67bd-4064-92d4-0d696ed1982c/Docker Swarm Services - Grafana.pptx",
        "is_soft_link": False,
        "last_modified": "2022-05-30 15:14:00+00",
        "location_id": "0",
        "location": "simcore.s3",
        "node_id": "dbc18a00-67bd-4064-92d4-0d696ed1982c",
        "node_name": "Docker Swarm Services - Grafana.pptx",
        "object_name": "1b3623fa-e02b-11ec-8777-02420a0194f6/dbc18a00-67bd-4064-92d4-0d696ed1982c/Docker Swarm Services - Grafana.pptx",
        "parent_id": "1b3623fa-e02b-11ec-8777-02420a0194f6/dbc18a00-67bd-4064-92d4-0d696ed1982c",
        "project_id": "1b3623fa-e02b-11ec-8777-02420a0194f6",
        "project_name": "New Study (1)",
        "raw_file_path": "1b3623fa-e02b-11ec-8777-02420a0194f6/dbc18a00-67bd-4064-92d4-0d696ed1982c/Docker Swarm Services - Grafana.pptx",
        "user_id": "3",
        "user_name": None,
    },
    # datcore
    {
        "bucket_name": "N:dataset:8fac2b22-b5c6-44f8-bf30-87a6c0bebad5",
        "created_at": "2020-05-28T15:48:34.386302+00:00",
        "display_file_path": "templatetemplate.json",
        "entity_tag": None,
        "file_id": "N:package:ce145b61-7e4f-470b-a113-033653e86d3d",
        "file_name": "templatetemplate.json",
        "file_size": 238,
        "file_uuid": "Kember Cardiac Nerve Model/templatetemplate.json",
        "is_soft_link": False,
        "last_modified": "2020-05-28T15:48:37.507387+00:00",
        "location_id": 1,
        "location": "datcore",
        "node_id": None,
        "node_name": None,
        "object_name": "Kember Cardiac Nerve Model/templatetemplate.json",
        "parent_id": "",
        "project_id": None,
        "project_name": None,
        "raw_file_path": None,
        "user_id": None,
        "user_name": None,
    },
]

_KEYS_IN_NEW_INTERFACE = (
    "created_at",
    "entity_tag",
    "file_id",
    "file_name",
    "file_size",
    "file_uuid",
    "is_soft_link",
    "last_modified",
    "location_id",
    "node_name",
    "project_name",
)


def _test_parameters() -> list[tuple[FileMetaDataEx, FileMetaDataGet]]:
    params = []
    for fmd_dict in _EXAMPLE_OLD_FILEMETADATA_EX:
        parent_id = fmd_dict.pop("parent_id")
        fmd = FileMetaData(**fmd_dict)
        fmd_ex = FileMetaDataEx(fmd=fmd, parent_id=parent_id)
        filtered_dict = {
            key: fmd_dict[key] for key in fmd_dict if key in _KEYS_IN_NEW_INTERFACE
        }
        api_fmd = FileMetaDataGet.parse_obj(filtered_dict)
        params.append((fmd_ex, api_fmd))
    return params


@pytest.mark.parametrize(
    "internal_fmd, expected_api_fmd",
    _test_parameters(),
)
def test_convert_to_api_fmd(
    internal_fmd: dict[str, Any], expected_api_fmd: FileMetaDataGet
):
    assert convert_to_api_fmd(internal_fmd) == expected_api_fmd
