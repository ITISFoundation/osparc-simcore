# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

pytest_simcore_core_services_selection = ["postgres", "migration"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


def test_migration_service_runs_correctly(docker_stack: dict): ...
