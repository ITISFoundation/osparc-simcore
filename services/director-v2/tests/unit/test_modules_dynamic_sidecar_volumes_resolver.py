# pylint: disable=redefined-outer-name

import os
from pathlib import Path
from typing import Any, Callable, Dict, List
from uuid import UUID

import pytest
from faker import Faker
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from simcore_service_director_v2.modules.dynamic_sidecar.volumes_resolver import (
    DynamicSidecarVolumesPathsResolver,
)


# FIXTURES
@pytest.fixture
def compose_namespace(faker: Faker) -> str:
    return f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_{faker.uuid4()}"


@pytest.fixture(scope="module")
def swarm_stack_name() -> str:
    return "test_swarm_stack_name"


@pytest.fixture
def node_uuid(faker: Faker) -> UUID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def state_paths() -> List[Path]:
    return [Path(f"/tmp/asd/asd/{x}") for x in range(10)]


@pytest.fixture
def run_id(faker: Faker) -> UUID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def expected_volume_config(
    swarm_stack_name: str, node_uuid: UUID, run_id: UUID
) -> Callable[[str, str], Dict[str, Any]]:
    def _callable(source: str, target: str) -> Dict[str, Any]:
        return {
            "Target": target,
            "Type": "volume",
            "VolumeOptions": {
                "Labels": {
                    "source": source,
                    "run_id": f"{run_id}",
                    "swarm_stack_name": swarm_stack_name,
                    "uuid": f"{node_uuid}",
                }
            },
        }

    return _callable


# TESTS


def test_expected_paths(
    swarm_stack_name: str,
    compose_namespace: str,
    node_uuid: UUID,
    state_paths: List[Path],
    expected_volume_config: Callable[[str, str], Dict[str, Any]],
    run_id: UUID,
) -> None:
    fake = Faker()

    inputs_path = Path(fake.file_path(depth=3)).parent
    assert DynamicSidecarVolumesPathsResolver.mount_entry(
        swarm_stack_name, compose_namespace, inputs_path, node_uuid, run_id
    ) == expected_volume_config(
        source=f"{compose_namespace}{f'{inputs_path}'.replace('/', '_')}",
        target=str(Path("/dy-volumes") / inputs_path.relative_to("/")),
    )

    outputs_path = Path(fake.file_path(depth=3)).parent
    assert DynamicSidecarVolumesPathsResolver.mount_entry(
        swarm_stack_name, compose_namespace, outputs_path, node_uuid, run_id
    ) == expected_volume_config(
        source=f"{compose_namespace}{f'{outputs_path}'.replace('/', '_')}",
        target=str(Path("/dy-volumes") / outputs_path.relative_to("/")),
    )

    for path in state_paths:
        name_from_path = f"{path}".replace(os.sep, "_")
        assert DynamicSidecarVolumesPathsResolver.mount_entry(
            swarm_stack_name, compose_namespace, path, node_uuid, run_id
        ) == expected_volume_config(
            source=f"{compose_namespace}{name_from_path}",
            target=str(Path("/dy-volumes/") / path.relative_to("/")),
        )
