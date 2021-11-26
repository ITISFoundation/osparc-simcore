# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# from simcore_postgres_database.models.projects import projects as projects_table

import json
import urllib.parse
from pathlib import Path
from typing import Dict
from urllib.parse import parse_qs

import pytest
from models_library.projects import Project
from pydantic import ConfigError, ValidationError, validator
from pydantic.main import BaseModel
from pydantic.networks import HttpUrl
from pytest_simcore.helpers.utils_services import list_fake_file_consumers
from simcore_service_webserver.constants import APP_JSONSCHEMA_SPECS_KEY
from simcore_service_webserver.projects import projects_api
from simcore_service_webserver.studies_dispatcher._projects import (
    UserInfo,
    ViewerInfo,
    create_viewer_project_model,
)
from simcore_service_webserver.studies_dispatcher.handlers_redirects import (
    RedirectionQueryParams,
)
from yarl import URL


@pytest.fixture
def project_jsonschema(project_schema_file: Path) -> Dict:
    return json.loads(project_schema_file.read_text())


def test_download_link_validators():

    params = RedirectionQueryParams(
        file_name="dataset_description.slsx",
        file_size=24770,  # BYTES
        file_type="MSExcel",
        viewer_key="simcore/services/dynamic/fooo",
        viewer_version="1.0.0",
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


@pytest.mark.parametrize("view", list_fake_file_consumers())
async def test_create_project_with_viewer(project_jsonschema, view):

    view["label"] = view.pop("display_name")
    viewer = ViewerInfo(**view)
    assert viewer.dict() == view

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
    await projects_api.validate_project(
        app={APP_JSONSCHEMA_SPECS_KEY: {"projects": project_jsonschema}},
        project=project_in,
    )


@pytest.mark.parametrize(
    "url_in,expected_download_link",
    [
        (
            "http://localhost:9081/view?file_type=CSV&download_link=https%253A%252F%252Fraw.githubusercontent.com%252Frawgraphs%252Fraw%252Fmaster%252Fdata%252Forchestra.csv&file_name=orchestra.json&file_size=4&viewer_key=simcore/services/comp/foo&viewer_version=1.0.0",
            "https://raw.githubusercontent.com/rawgraphs/raw/master/data/orchestra.csv",
        ),
        (
            "http://127.0.0.1:9081/view?file_type=IPYNB&viewer_key=simcore/services/dynamic/jupyter-octave-python-math&viewer_version=1.6.9&file_size=1&download_link=https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%2520samples/sample.ipynb",
            "https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%20samples/sample.ipynb",
        ),
    ],
)
def test_validation_of_redirection_urls(url_in, expected_download_link):
    #
    #  %  -> %25
    #  space -> %20
    #
    url_in = URL(url_in)

    assert hasattr(url_in, "query")  # as a Request
    params = RedirectionQueryParams.from_request(url_in)

    assert params.download_link == expected_download_link

    redirected_url = URL(
        r"http://localhost:9081/#/error?message=Invalid+parameters+%5B%0A+%7B%0A++%22loc%22:+%5B%0A+++%22download_link%22%0A++%5D,%0A++%22msg%22:+%22invalid+or+missing+URL+scheme%22,%0A++%22type%22:+%22value_error.url.scheme%22%0A+%7D%0A%5D&status_code=400"
    )
    print(redirected_url.fragment)


def test_url_quoting_and_validation():
    # The URL quoting functions focus on taking program data and making it safe for use
    # as URL components by quoting special characters and appropriately encoding non-ASCII text.
    # They also support reversing these operations to recreate the original data from the contents
    # of a URL component if that task isn’t already covered by the URL parsing functions above
    SPACE = " "

    class M(BaseModel):
        url: HttpUrl

        @validator("url", pre=True)
        @classmethod
        def unquote_url(cls, v):
            w = urllib.parse.unquote(v)
            if SPACE in w:
                w = w.replace(SPACE, "%20")
            return w

    M.parse_obj(
        {
            # encoding %20 as %2520
            "url": "https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%2520samples/sample.ipynb"
        }
    )

    obj2 = M.parse_obj(
        {
            # encoding space as %20
            "url": "https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%20samples/sample.ipynb"
        }
    )

    url_with_url_in_query = "http://127.0.0.1:9081/view?file_type=IPYNB&viewer_key=simcore/services/dynamic/jupyter-octave-python-math&viewer_version=1.6.9&file_size=1&download_link=https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%2520samples/sample.ipynb"
    obj4 = M.parse_obj({"url": URL(url_with_url_in_query).query["download_link"]})

    assert obj2.url.path == obj4.url.path

    quoted_url = urllib.parse.quote(
        "https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%20samples/sample.ipynb"
    )
    M(url=quoted_url)
    M.parse_obj({"url": url_with_url_in_query})

    assert (
        URL(url_with_url_in_query).query["download_link"]
        == "https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%20samples/sample.ipynb"
    )

    # NOTE: BEFORE we had a decode_download_link-----
    obj5 = RedirectionQueryParams.parse_obj(
        {
            "file_type": "IPYNB",
            "viewer_key": "simcore/services/dynamic/jupyter-octave-python-math",
            "viewer_version": "1.6.9",
            "file_size": "1",
            "download_link": "https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%20samples/sample.ipynb",
        }
    )

    params = dict(URL(url_with_url_in_query).query)

    RedirectionQueryParams.parse_obj(params)

    with pytest.raises((ConfigError, ValidationError)):
        RedirectionQueryParams.from_orm(URL(url_with_url_in_query).query)

    assert params == {k: str(v) for k, v in obj5.dict(exclude_unset=True).items()}
