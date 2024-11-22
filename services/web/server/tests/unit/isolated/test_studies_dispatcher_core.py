# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
import urllib.parse
from typing import Any

import pytest
from models_library.projects import Project, ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import field_validator
from pydantic.main import BaseModel
from pydantic.networks import HttpUrl
from pytest_simcore.helpers.webserver_fake_services_data import list_fake_file_consumers
from simcore_service_webserver.studies_dispatcher._projects import (
    UserInfo,
    ViewerInfo,
    _create_project_with_filepicker_and_service,
)
from yarl import URL


@pytest.mark.parametrize("view", list_fake_file_consumers())
async def test_create_project_with_viewer(view: dict[str, Any]):

    view["label"] = view.pop("display_name")
    viewer = ViewerInfo(**view)

    user = UserInfo(id=3, name="foo", primary_gid=33, email="foo@bar.com")

    project = _create_project_with_filepicker_and_service(
        project_id=ProjectID("e3ee7dfc-25c3-11eb-9fae-02420a01b846"),
        file_picker_id=NodeID("4c69c0ce-00e4-4bd5-9cf0-59b67b3a9343"),
        viewer_id=NodeID("fc718e5a-bf07-4abe-b526-d9cafd34830c"),
        owner=user,
        download_link="http://httpbin.org/image/jpeg",
        viewer_info=viewer,
    )

    assert isinstance(project, Project)

    assert list(project.workbench.keys())

    # converts into equivalent Dict
    project_in: dict = json.loads(project.model_dump_json(exclude_none=True, by_alias=True))
    print(json.dumps(project_in, indent=2))

    # This operation is done exactly before adding to the database in projects_handlers.create_projects
    Project.model_validate(project_in)


def test_url_quoting_and_validation():
    # The URL quoting functions focus on taking program data and making it safe for use
    # as URL components by quoting special characters and appropriately encoding non-ASCII text.
    # They also support reversing these operations to recreate the original data from the contents
    # of a URL component if that task isn’t already covered by the URL parsing functions above
    SPACE = " "

    class M(BaseModel):
        url: HttpUrl

        @field_validator("url", mode="before")
        @classmethod
        def unquote_url(cls, v):
            w = urllib.parse.unquote(v)
            if SPACE in w:
                w = w.replace(SPACE, "%20")
            return w

    M.model_validate(
        {
            # encoding %20 as %2520
            "url": "https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%2520samples/sample.ipynb"
        }
    )

    obj2 = M.model_validate(
        {
            # encoding space as %20
            "url": "https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%20samples/sample.ipynb"
        }
    )

    url_with_url_in_query = "http://127.0.0.1:9081/view?file_type=IPYNB&viewer_key=simcore/services/dynamic/jupyter-octave-python-math&viewer_version=1.6.9&file_size=1&download_link=https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%2520samples/sample.ipynb"
    obj4 = M.model_validate({"url": URL(url_with_url_in_query).query["download_link"]})

    assert obj2.url.path == obj4.url.path

    quoted_url = urllib.parse.quote(
        "https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%20samples/sample.ipynb"
    )
    M(url=quoted_url)
    M.model_validate({"url": url_with_url_in_query})

    assert (
        URL(url_with_url_in_query).query["download_link"]
        == "https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%20samples/sample.ipynb"
    )
