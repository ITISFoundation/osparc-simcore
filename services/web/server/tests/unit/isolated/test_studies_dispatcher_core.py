# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# from simcore_postgres_database.models.projects import projects as projects_table

import json
from pathlib import Path
from typing import Dict
from urllib.parse import parse_qs

import pytest
from yarl import URL

from models_library.projects import Project
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

    params = QueryParams(
        file_name="dataset_description.slsx",
        file_size=24770,  # BYTES
        file_type="MSExcel",
        download_link="https://blackfynn-discover-use1.s3.amazonaws.com/23/2/files/dataset_description.xlsx?AWSAccessKeyId=AKIAQNJEWKCFAOLGQTY6&Signature=K229A0CE5Z5OU2PRi2cfrfgLLEw%3D&x-amz-request-payer=requester&Expires=1605545606",
    )
    assert params.download_link.host.endswith("s3.amazonaws.com")
    assert params.download_link.host_type == "domain"

    # TODO: cannot validate amazon download links with HEAD because only operation allowed is GET
    ## await p.check_download_link()

    query = parse_qs(params.download_link.query)
    assert {"AWSAccessKeyId", "Signature", "Expires", "x-amz-request-payer"} == set(
        query.keys()
    )


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

    assert isinstance(project, Project)

    assert list(project.workbench.keys())

    # converts into equivalent Dict
    project_in: Dict = json.loads(project.json(exclude_none=True, by_alias=True))
    print(json.dumps(project_in, indent=2))

    # This operation is done exactly before adding to the database in projects_handlers.create_projects
    projects_api.validate_project(
        app={APP_JSONSCHEMA_SPECS_KEY: {"projects": project_jsonschema}},
        project=project_in,
    )


def test_redirection_urls():
    url_in = URL(
        r"http://localhost:9081/view?file_type=CSV&download_link=https%253A%252F%252Fraw.githubusercontent.com%252Frawgraphs%252Fraw%252Fmaster%252Fdata%252Forchestra.csv&file_name=orchestra.json&file_size=4"
    )

    # TODO: why this fails?
    # assert (
    #    url_in.query["download_link"]
    #    == "https%253A%252F%252Fraw.githubusercontent.com%252Frawgraphs%252Fraw%252Fmaster%252Fdata%252Forchestra.csv"
    # )

    assert hasattr(url_in, "query")
    params = QueryParams.from_request(url_in)

    assert (
        params.download_link
        == "https://raw.githubusercontent.com/rawgraphs/raw/master/data/orchestra.csv"
    )

    redirected_url = URL(
        r"http://localhost:9081/#/error?message=Invalid+parameters+%5B%0A+%7B%0A++%22loc%22:+%5B%0A+++%22download_link%22%0A++%5D,%0A++%22msg%22:+%22invalid+or+missing+URL+scheme%22,%0A++%22type%22:+%22value_error.url.scheme%22%0A+%7D%0A%5D&status_code=400"
    )
    print(redirected_url.fragment)
