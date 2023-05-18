"""
    Usage example

    def test_it(faker: Faker):
        fake_docker_compose = generate_fake_docker_compose(faker, 3)

        print(fake_docker_compose)

"""

from typing import Any

from faker import Faker

_RANDOM = -1


def _range(faker: Faker, num_items: int = _RANDOM, min_: int = 1, max_: int = 4):
    if num_items == _RANDOM:
        num_items = faker.random_int(min=min_, max=max_)
    return range(num_items)


def generate_fake_docker_compose(
    faker: Faker, num_services: int = _RANDOM
) -> dict[str, Any]:
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
        service_name, service = generate_fake_service_specs(faker)

        docker_compose["services"][service_name] = service

    return docker_compose


def generate_fake_service_specs(faker: Faker) -> tuple[str, dict[str, Any]]:
    service_name = faker.word()
    service = {
        "image": faker.word(),
        "environment": {faker.word(): faker.word() for _ in _range(faker, max_=10)},
        "ports": [
            f"{faker.random_int(1000, 9999)}:{faker.random_int(1000, 9999)}"
            for _ in _range(faker)
        ],
    }
    return service_name, service
