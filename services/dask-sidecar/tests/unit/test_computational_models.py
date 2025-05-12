import pytest
from faker import Faker
from pydantic import ByteSize, ValidationError
from simcore_service_dask_sidecar.computational_sidecar.models import (
    ContainerHostConfig,
)


def test_container_host_config_sets_swap_same_as_memory_if_not_set(faker: Faker):
    instance = ContainerHostConfig(
        Binds=[faker.pystr() for _ in range(5)],
        Memory=ByteSize(faker.pyint()),
        NanoCPUs=faker.pyint(min_value=1),
    )
    assert instance.memory == instance.memory_swap


def test_container_host_config_raises_if_set_negative(
    faker: Faker,
):
    with pytest.raises(ValidationError):
        ContainerHostConfig(
            Binds=[faker.pystr() for _ in range(5)],
            Memory=ByteSize(faker.pyint(min_value=234)),
            NanoCPUs=faker.pyint(min_value=1),
            MemorySwap=ByteSize(faker.pyint(min_value=-84654, max_value=-1)),
        )


def test_container_host_config_raises_if_set_smaller_than_memory(
    faker: Faker,
):
    with pytest.raises(ValidationError):
        ContainerHostConfig(
            Binds=[faker.pystr() for _ in range(5)],
            Memory=ByteSize(faker.pyint(min_value=234)),
            NanoCPUs=faker.pyint(min_value=1),
            MemorySwap=ByteSize(0),
        )
    with pytest.raises(ValidationError):
        ContainerHostConfig(
            Binds=[faker.pystr() for _ in range(5)],
            Memory=ByteSize(faker.pyint(min_value=234)),
            NanoCPUs=faker.pyint(min_value=1),
            MemorySwap=ByteSize(faker.pyint(min_value=1, max_value=233)),
        )


def test_container_host_config_sets_swap_if_set_bigger_than_memory(
    faker: Faker,
):
    instance = ContainerHostConfig(
        Binds=[faker.pystr() for _ in range(5)],
        Memory=ByteSize(faker.pyint(min_value=234, max_value=434234)),
        NanoCPUs=faker.pyint(min_value=1),
        MemorySwap=ByteSize(faker.pyint(min_value=434235, max_value=12343424234)),
    )
    assert instance.memory_swap
    assert instance.memory < instance.memory_swap
