# pylint:disable=redefined-outer-name

import pytest
from faker import Faker
from models_library.projects_nodes_io import NodeID
from simcore_service_director_v2.modules.api_key_resource_manager import (
    get_api_key_name,
)


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


def test_get_api_key_name_is_not_randomly_generated(node_id: NodeID):
    api_key_names = {get_api_key_name(node_id) for x in range(1000)}
    assert len(api_key_names) == 1


# TODO: write a layer to mock RPC requests
