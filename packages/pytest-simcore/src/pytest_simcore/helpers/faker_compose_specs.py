from typing import Any

from faker import Faker
from pydantic import ByteSize, TypeAdapter
from servicelib.resources import USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY, USER_SERVICE_MEM_RESOURCE_LIMIT_ENV_KEY


def _range(faker: Faker, num_items: int | None = None, min_: int = 1, max_: int = 4) -> range:
    if num_items is None:
        num_items = faker.random_int(min=min_, max=max_)
    return range(num_items)


def _generate_fake_service_specs(faker: Faker) -> tuple[str, dict[str, Any]]:
    service_name = faker.word()
    service = {
        "image": faker.word(),
        "environment": {faker.word(): faker.word() for _ in _range(faker, max_=10)},
    }
    return service_name, service


def generate_fake_docker_compose(faker: Faker, num_services: int | None = None) -> dict[str, Any]:
    """
    Fakes https://docs.docker.com/compose/compose-file/compose-file-v3/

    """
    faker = Faker()

    docker_compose = {
        "version": "3",
        "services": {},
    }

    # SEE https://faker.readthedocs.io/en/master/providers/baseprovider.html?highlight=random

    for _ in _range(faker, num_services, max_=4):
        service_name, service = _generate_fake_service_specs(faker)

        docker_compose["services"][service_name] = service

    return docker_compose


def inject_container_resources(
    compose_spec: dict[str, Any],
    *,
    nano_cpus: int = int(1.0 * 1e9),
    memory_bytes: int = TypeAdapter(ByteSize).validate_python("1GiB"),
) -> dict[str, Any]:
    """Injects SIMCORE resource env vars and deploy limits into every service of a compose spec"""

    for service in compose_spec.get("services", {}).values():
        env = service.get("environment")
        if env is None:
            service["environment"] = env = []
        if isinstance(env, dict):
            env[USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY] = f"{nano_cpus}"
            env[USER_SERVICE_MEM_RESOURCE_LIMIT_ENV_KEY] = f"{memory_bytes}"
        else:
            assert isinstance(env, list)  # nosec
            env.extend(
                [
                    f"{USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY}={nano_cpus}",
                    f"{USER_SERVICE_MEM_RESOURCE_LIMIT_ENV_KEY}={memory_bytes}",
                ]
            )

        deploy = service.setdefault("deploy", {})
        resources = deploy.setdefault("resources", {})
        limits = resources.setdefault("limits", {})
        cpus = nano_cpus / 1e9
        limits["cpus"] = f"{cpus}"
        limits["memory"] = f"{memory_bytes}"
    return compose_spec
