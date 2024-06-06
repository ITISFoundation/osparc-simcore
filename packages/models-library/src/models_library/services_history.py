import random
from datetime import datetime

from pydantic import BaseModel

from .services_constrained_types import ServiceKey, ServiceVersion

# NOTE: see https://peps.python.org/pep-0440/#version-specifiers
# SEE https://peps.python.org/pep-0440/#compatible-release


class ServiceRelease(BaseModel):
    version: ServiceVersion
    release_date: datetime
    compatible_with: list[ServiceVersion]


class Service(BaseModel):
    # here should go all the info we have now
    name: ServiceKey
    name_display: str
    version: ServiceVersion
    version_display: str
    release_date: datetime

    # TODO: UNBOUND!
    # TODO: what about compatible with other service key?
    compatible_with: list[ServiceVersion]

    # TODO: UNBOUND! Could be limited using filters
    history: list[ServiceRelease]


#
# just for testing purposes
#


def generate_fake_service_release(faker) -> ServiceRelease:

    return ServiceRelease(
        version=f"{faker.pyint(0, 2)}.{faker.pyint(0, 5)}.{faker.pyint(0, 9)}-{'alpha' if random.choice([True, False]) else 'beta'}.{faker.pyint(1, 5)}",
        release_date=faker.date_between(start_date="-1y", end_date="today"),
    )


def generate_fake_service_data(faker) -> dict:
    history = [generate_fake_service_release(faker) for _ in range(5)]
    history_versions = [release.version for release in history]
    current_version = f"{faker.pyint(0, 2)}.{faker.pyint(0, 5)}.{faker.pyint(0, 9)}"
    return {
        "name": faker.company(),
        "version": current_version,
        "version_display": faker.catch_phrase(),
        "release_date": faker.date_between(start_date="-1y", end_date="today"),
        "history": history,
    }
