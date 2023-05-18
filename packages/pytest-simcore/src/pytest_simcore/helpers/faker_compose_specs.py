"""
    Usage example

    def test_it(faker: Faker):
        fake_docker_compose = generate_fake_docker_compose(faker, 3)

        print(fake_docker_compose)

"""

from typing import Any

from faker import Faker

_RANDOM = -1


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

    if num_services is _RANDOM:
        num_services = faker.random_digit_not_null_or_empty()  # [1, 9]

    assert num_services > 0

    for _ in range(num_services):
        service_name, service = generate_fake_service_specs(faker)

        docker_compose["services"][service_name] = service

    return docker_compose


def generate_fake_service_specs(faker: Faker) -> tuple[str, dict[str, Any]]:

    service_name = faker.word()
    service = {
        "image": faker.word(),
        "environment": {faker.word(): faker.word() for _ in faker.random_digit()},
        "ports": [
            f"{faker.random_int(1000, 9999)}:{faker.random_int(1000, 9999)}"
            for _ in faker.random_digit()
        ],
    }
    return service_name, service
