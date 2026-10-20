from pathlib import Path

from pytest_simcore.docker_swarm import _list_owned_migration_services
from pytest_simcore.helpers.stack_names import compute_stack_names, get_checkout_token


class _FakeService:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeServices:
    def __init__(self, services: list[_FakeService]) -> None:
        self._services = services

    def list(self) -> list[_FakeService]:
        return self._services


class _FakeClient:
    def __init__(self, services: list[_FakeService]) -> None:
        self.services = _FakeServices(services)


def test_migration_services_are_selected_by_exact_name():
    # the hazard: when the branch fragment itself contains "migration", a substring match
    # would select EVERY service this checkout deployed (postgres, redis, ...)
    core_stack, _ = compute_stack_names("fix/migration", get_checkout_token(Path("/home/dev/simcore")))
    assert "migration" in core_stack

    own_services = [f"{core_stack}_{key}" for key in ("postgres", "redis", "migration")]
    # a co-tenant checkout on the same branch has its own migration service, which must
    # be left alone
    co_tenant = "pytest-fix-migration-core-ffff_migration"
    client = _FakeClient([_FakeService(name) for name in (*own_services, co_tenant)])

    owned = _list_owned_migration_services(client, core_stack)  # type: ignore[arg-type]

    assert [str(service.name) for service in owned] == [f"{core_stack}_migration"]
