# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from pathlib import Path
from typing import Dict
from urllib.parse import parse_qs

import pytest

from simcore_service_webserver.constants import APP_JSONSCHEMA_SPECS_KEY
from simcore_service_webserver.projects import projects_api
from simcore_service_webserver.studies_dispatcher._core import _FILETYPE_TO_VIEWER
from simcore_service_webserver.studies_dispatcher._projects import (
    UserInfo,
    ViewerInfo,
    create_viewer_project_model,
)
from simcore_service_webserver.studies_dispatcher.handlers_redirects import QueryParams


@pytest.fixture
def project_jsonschema(project_schema_file: Path) -> Dict:
    return json.loads(project_schema_file.read_text())


async def test_download_link_validators():

    p = QueryParams(
        file_name="dataset_description.slsx",
        file_size=24770,  # BYTES
        file_type="MSExcel",
        download_link="https://blackfynn-discover-use1.s3.amazonaws.com/23/2/files/dataset_description.xlsx?AWSAccessKeyId=AKIAQNJEWKCFAOLGQTY6&Signature=K229A0CE5Z5OU2PRi2cfrfgLLEw%3D&x-amz-request-payer=requester&Expires=1605545606",
    )
    assert p.download_link.host.endswith("s3.amazonaws.com")
    assert p.download_link.host_type == "domain"

    query = parse_qs(p.download_link.query)
    assert {"AWSAccessKeyId", "Signature", "Expires", "x-amz-request-payer"} == set(
        query.keys()
    )

    # TODO: cannot validate amazon download links with HEAD because only operation allowed is GET
    ## await p.check_download_link()


@pytest.mark.parametrize(
    "file_type,viewer", [(k, v) for k, v in _FILETYPE_TO_VIEWER.items()]
)
def test_create_project_with_viewer(
    project_jsonschema, file_type: str, viewer: ViewerInfo
):
    user = UserInfo(id=3, name="foo", primary_gid=33, email="foo@bar.com")

    project = create_viewer_project_model(
        project_id="e3ee7dfc-25c3-11eb-9fae-02420a01b846",
        file_picker_id="4c69c0ce-00e4-4bd5-9cf0-59b67b3a9343",
        viewer_id="fc718e5a-bf07-4abe-b526-d9cafd34830c",
        owner=user,
        download_link="http://httpbin.org/image/jpeg",
        viewer_info=viewer,
    )

    print(project.json(indent=2))

    # This operation is done exactly before adding to the database in projects_handlers.create_projects
    projects_api.validate_project(
        app={APP_JSONSCHEMA_SPECS_KEY: {"projects": project_jsonschema}},
        project=json.loads(project.json()),
    )

    # can convert to db?


def test_map_file_types_to_viewers():
    pass


def test_create_guest_user():
    pass


def test_portal_workflow():
    pass
