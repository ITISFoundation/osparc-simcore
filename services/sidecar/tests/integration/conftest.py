import logging
import sys

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
# TODO: this should be done as a real pytest plugin instead
sys.path.append(str(current_dir / '../../../../packages'))
print(sys.path)
# imports the fixtures for the integration tests
pytest_plugins = [
    "pytest-fixtures.docker_compose",
    "pytest-fixtures.docker_swarm",
    "pytest-fixtures.docker_registry",
    "pytest-fixtures.rabbit_service",
    "pytest-fixtures.celery_service",
    "pytest-fixtures.postgres_service",
    "pytest-fixtures.redis_service",
    "pytest-fixtures.websocket_client"
]
log = logging.getLogger(__name__)
