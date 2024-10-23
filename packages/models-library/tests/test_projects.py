# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from copy import deepcopy
from typing import Any

import pytest
from faker import Faker
from models_library.api_schemas_webserver.projects import LongTruncatedStr, ProjectPatch
from models_library.projects import Project


@pytest.fixture()
def minimal_project(faker: Faker) -> dict[str, Any]:
    # API request body payload
    return {
        "uuid": faker.uuid4(),
        "name": "The project name",
        "description": "The project's description",
        "prjOwner": "theowner@ownership.com",
        "accessRights": {},
        "thumbnail": None,
        "creationDate": "2019-05-24T10:36:57.813Z",
        "lastChangeDate": "2019-05-24T10:36:57.813Z",
        "workbench": {},
    }


def test_project_minimal_model(minimal_project: dict[str, Any]):
    project = Project.model_validate(minimal_project)
    assert project

    assert project.thumbnail is None


def test_project_with_thumbnail_as_empty_string(minimal_project: dict[str, Any]):
    thumbnail_empty_string = deepcopy(minimal_project)
    thumbnail_empty_string.update({"thumbnail": ""})
    project = Project.model_validate(thumbnail_empty_string)

    assert project
    assert project.thumbnail is None


def test_project_patch_truncates_description():
    # NOTE: checks https://github.com/ITISFoundation/osparc-simcore/issues/5988
    assert LongTruncatedStr.curtail_length
    len_truncated = int(LongTruncatedStr.curtail_length)

    long_description = "X" * (len_truncated + 10)
    assert len(long_description) > len_truncated

    update = ProjectPatch(description=long_description)
    assert len(update.description) == len_truncated

    short_description = "X"
    update = ProjectPatch(description=short_description)
    assert len(update.description) == len(short_description)
