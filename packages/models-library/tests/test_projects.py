# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from copy import deepcopy
from typing import Any

import pytest
from faker import Faker
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
    project = Project.parse_obj(minimal_project)
    assert project

    assert project.thumbnail is None


def test_project_with_thumbnail_as_empty_string(minimal_project: dict[str, Any]):
    thumbnail_empty_string = deepcopy(minimal_project)
    thumbnail_empty_string.update({"thumbnail": ""})
    project = Project.parse_obj(thumbnail_empty_string)

    assert project
    assert project.thumbnail is None


def test_project_type_in_models_package_same_as_in_postgres_database_package():
    from models_library.projects import ProjectType as ml_project_type
    from simcore_postgres_database.models.projects import ProjectType as pg_project_type

    # pylint: disable=no-member
    assert (
        ml_project_type.__members__.keys() == pg_project_type.__members__.keys()
    ), f"The enum in models_library package and postgres package shall have the same values. models_pck: {ml_project_type.__members__}, postgres_pck: {pg_project_type.__members__}"
