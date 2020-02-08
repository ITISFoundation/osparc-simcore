# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from pathlib import Path
import os
import sys

import sqlalchemy as sa

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope='session')
def environ_context():
    keep = os.environ.copy()

    # config database
    os.environ['POSTGRES_DB']="test"
    os.environ['POSTGRES_USER']="test"
    os.environ['POSTGRES_PASSWORD']="test"
    os.environ['POSTGRES_HOST']='127.0.0.1'
    os.environ['POSTGRES_PORT']= '5432'

    os.environ['TESTING']='True'

    yield

    os.environ = keep


@pytest.fixture(scope='session')
def docker_compose_file(environ_context):
    """ Overrides pytest-docker fixture """

    # docker-compose reads these environs
    file_path = current_dir / 'docker-compose.yml'
    assert file_path.exists()

    yield str(file_path)


def is_postgres_responsive(url: str):
    """Check if something responds to ``url`` """
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True


@pytest.fixture(scope='session')
def postgres_service(docker_services, docker_ip, environ_context):

    url = "postgresql://{e[POSTGRES_USER]}:{e[POSTGRES_PASSWORD]}@{e[POSTGRES_HOST]}:{e[POSTGRES_PORT]}/{e[POSTGRES_DB]}".format(e=os.environ)

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: is_postgres_responsive(url),
        timeout=30.0,
        pause=0.1,
    )

    return url
