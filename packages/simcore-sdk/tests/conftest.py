import pytest
import os
# pylint:disable=unused-argument

pytest_plugins = ["tests.fixtures.postgres"]

@pytest.fixture(scope='session')
def docker_compose_file(pytestconfig):
    my_path = os.path.join(os.path.dirname(__file__), 'docker-compose.yml')
    return my_path
