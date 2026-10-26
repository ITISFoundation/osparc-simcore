# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Unit tests for the comp_tasks helpers that size a node for its pricing unit's machine."""

from typing import Any, Final
from unittest import mock
from uuid import uuid4

import pytest
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.resource_tracker import HardwareInfo
from pytest_mock import MockerFixture
from pytest_simcore.helpers.project_nodes_pricing import (
    T3_MEDIUM_NAME,
    get_fixed_ec2_instance_types,
    single_container_required_resources,
)
from simcore_service_director_v2.core.errors import MultiContainerOverrideNotSupportedError
from simcore_service_director_v2.modules.db.repositories.comp_tasks import _utils


def _multi_container_resources() -> dict[str, Any]:
    # sub-service names differ from DEFAULT_SINGLE_SERVICE_NAME ("container"),
    # which is what marks the payload as a multi-container service
    main = single_container_required_resources("library/nginx:latest", cpu=0.1, ram_bytes=2 * 1024**3)["container"]
    sidecar = single_container_required_resources("library/nginx:latest", cpu=0.1, ram_bytes=1536 * 1024**2)[
        "container"
    ]
    return {"main": main, "sidecar": sidecar}


_MULTI: Final[dict[str, Any]] = _multi_container_resources()

_COMPUTATIONAL_KEY: Final[str] = "simcore/services/comp/itis/sleeper"
_DYNAMIC_KEY: Final[str] = "simcore/services/dynamic/jupyter-mock"


async def _update(mocker: MockerFixture, node_key: str, required_resources: dict[str, Any] = _MULTI):
    repo_cls = mocker.patch.object(_utils, "ProjectNodesRepo")
    repo_cls.return_value.get = mock.AsyncMock(return_value=mock.Mock(required_resources=required_resources))
    await _utils._update_project_node_resources_from_hardware_info(  # noqa: SLF001
        mock.Mock(),
        is_wallet=True,
        project_id=ProjectID(f"{uuid4()}"),
        node_id=NodeID(f"{uuid4()}"),
        node_key=node_key,
        hardware_info=HardwareInfo(aws_ec2_instances=[T3_MEDIUM_NAME]),
        ec2_instance_types=get_fixed_ec2_instance_types({T3_MEDIUM_NAME}),
    )
    return repo_cls


async def test_node_resources_update_rejects_multi_container_computational_service(
    mocker: MockerFixture,
):
    # a multi-container computational node runs as a dask worker sized for the
    # machine: per-sub-service sizing is not implemented, so the computation start
    # must fail instead of running it silently unsized
    with pytest.raises(MultiContainerOverrideNotSupportedError) as exc_info:
        await _update(mocker, _COMPUTATIONAL_KEY)

    assert exc_info.value.error_context()["sub_service_names"] == {"main", "sidecar"}


async def test_node_resources_update_keeps_multi_container_dynamic_node_unsized(
    mocker: MockerFixture,
):
    # a dynamic node brings its own per-container resources: leaving a
    # multi-container one unsized is harmless, so the previous no-op is preserved
    # (it must NOT abort the whole computation, e.g. when a comp node is the only one started)
    repo_cls = await _update(mocker, _DYNAMIC_KEY)
    repo_cls.return_value.update.assert_not_called()


async def test_node_resources_update_skips_node_without_stored_resources(
    mocker: MockerFixture,
):
    # {} is the DB default (no override stored yet), not a multi-container service:
    # the node keeps its previous behavior (task image falls back to the catalog
    # resources) and must not abort the computation start
    repo_cls = await _update(mocker, _COMPUTATIONAL_KEY, required_resources={})
    repo_cls.return_value.update.assert_not_called()
