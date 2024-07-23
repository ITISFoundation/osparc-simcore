# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
"""
    Fixtures to produce fake data for a project:
        - it is self-consistent
        - granular customization by overriding fixtures
"""


import pytest
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import parse_obj_as

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
    return parse_obj_as(
        ProjectID,
        request.config.getoption("--faker-project-id", default=None) or faker.uuid4(),
    )


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return parse_obj_as(NodeID, faker.uuid4())
