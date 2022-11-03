from faker import Faker
from pydantic import ByteSize
from simcore_service_dask_sidecar.computational_sidecar.models import (
    ContainerHostConfig,
)


def test_container_host_config_sets_swap_same_as_memory_if_not_set(faker: Faker):
    instance = ContainerHostConfig(
        Binds=[faker.pystr() for _ in range(5)],
        Memory=ByteSize(faker.pyint()),
        NanoCPUs=faker.pyfloat(min_value=0.1),
    )
    assert instance.memory == instance.memory_swap


def test_container_host_config_sets_swap_same_as_memory_if_smaller_than_memory(
    faker: Faker,
):
    instance = ContainerHostConfig(
        Binds=[faker.pystr() for _ in range(5)],
        Memory=ByteSize(faker.pyint(min_value=234)),
        NanoCPUs=faker.pyfloat(min_value=0.1),
        MemorySwap=ByteSize(faker.pyint(min_value=0, max_value=233)),
    )
    assert instance.memory == instance.memory_swap


def test_container_host_config_sets_swap_disabled_if_set_negative(
    faker: Faker,
):
    instance = ContainerHostConfig(
        Binds=[faker.pystr() for _ in range(5)],
        Memory=ByteSize(faker.pyint(min_value=234)),
        NanoCPUs=faker.pyfloat(min_value=0.1),
        MemorySwap=ByteSize(faker.pyint(min_value=-84654, max_value=-1)),
    )
    assert instance.memory != instance.memory_swap
    assert instance.memory_swap == -1


def test_container_host_config_sets_swap_if_set_bigger_than_memory(
    faker: Faker,
):
    instance = ContainerHostConfig(
        Binds=[faker.pystr() for _ in range(5)],
        Memory=ByteSize(faker.pyint(min_value=234, max_value=434234)),
        NanoCPUs=faker.pyfloat(min_value=0.1),
        MemorySwap=ByteSize(faker.pyint(min_value=434235)),
    )
    assert instance.memory_swap
    assert instance.memory < instance.memory_swap
