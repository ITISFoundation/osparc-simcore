# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
"""
    Fixtures to produce fake data for a project:
        - it is self-consistent
        - granular customization by overriding fixtures
"""


from typing import Any

import pytest
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_simcore.helpers.faker_factories import random_project

_MESSAGE = (
    "If set, it overrides the fake value of `{}` fixture."
    " Can be handy when interacting with external/real APIs"
)


def pytest_addoption(parser: pytest.Parser):
    simcore_group = parser.getgroup("simcore")
    simcore_group.addoption(
        "--faker-project-id",
        action="store",
        type=str,
        default=None,
        help=_MESSAGE.format("project_id"),
    )


@pytest.fixture
def project_id(faker: Faker, request: pytest.FixtureRequest) -> ProjectID:
    return TypeAdapter(ProjectID).validate_python(
        request.config.getoption("--faker-project-id", default=None) or faker.uuid4(),
    )


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return TypeAdapter(NodeID).validate_python(faker.uuid4())


@pytest.fixture
def project_data(
    faker: Faker,
    project_id: ProjectID,
    user_id: UserID,
) -> dict[str, Any]:
    return random_project(fake=faker, uuid=f"{project_id}", prj_owner=user_id)
