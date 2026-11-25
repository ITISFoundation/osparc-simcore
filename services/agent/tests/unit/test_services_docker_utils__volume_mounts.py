# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiodocker import DockerError
from fastapi import FastAPI
from pytest_mock import MockerFixture
from simcore_service_agent.services.docker_utils import (
    get_unused_dynamic_sidecar_volumes,
    remove_volume,
)

_MOUNTPOINT_ROOT = "/var/lib/docker/volumes"

type RunRemoveVolume = Callable[[list[Exception | None]], Awaitable[AsyncMock]]


_RUNNING = {"Running": True}
_EXITED = {"Running": False}


def _fake_container(mounts: list[dict], state: dict) -> AsyncMock:
    container = AsyncMock()
    container.show.return_value = {"Mounts": mounts, "State": state}
    return container


def _fake_docker(
    volumes: list[dict] | None,
    container_mounts: list[list[dict]],
    states: list[dict] | None = None,
):
    docker = Mock()
    docker.volumes.list = AsyncMock(return_value={"Volumes": volumes})
    states = states or [_RUNNING] * len(container_mounts)
    containers = [_fake_container(mounts, state) for mounts, state in zip(container_mounts, states, strict=True)]
    docker.containers.list = AsyncMock(return_value=containers)
    return docker


def _dyv_volume(name: str) -> dict:
    return {"Name": name, "Mountpoint": f"{_MOUNTPOINT_ROOT}/{name}/_data"}


@pytest.mark.parametrize(
    "volumes,container_mounts,states,expected",
    [
        pytest.param(
            [_dyv_volume("dyv_a"), _dyv_volume("dyv_b"), _dyv_volume("dyv_c"), _dyv_volume("not_a_dyv")],
            [
                # dyv_a held by a volume mount; the unrelated bind marks nothing
                [{"Type": "volume", "Name": "dyv_a"}, {"Type": "bind", "Source": "/etc/something"}],
                # dyv_b held by an rclone mount container binding the volume mountpoint
                [{"Type": "bind", "Source": f"{_MOUNTPOINT_ROOT}/dyv_b/_data"}],
            ],
            [_RUNNING, _RUNNING],
            {"dyv_c"},
            id="classifies_volume_and_helper_bind_mounts",
        ),
        pytest.param(
            [_dyv_volume("dyv_a")],
            [[{"Type": "bind", "Source": f"{_MOUNTPOINT_ROOT}/dyv_a/_data/"}]],
            [_RUNNING],
            set(),
            id="helper_bind_with_trailing_slash_matches",
        ),
        pytest.param(
            [_dyv_volume("dyv_a")],
            [[{"Type": "bind", "Source": f"{_MOUNTPOINT_ROOT}/dyv_a/_data"}]],
            [_EXITED],
            {"dyv_a"},
            id="exited_rcm_does_not_pin_volume",
        ),
        pytest.param(None, [], [], set(), id="no_volumes"),
    ],
)
async def test_get_unused_dynamic_sidecar_volumes(
    volumes: list[dict] | None,
    container_mounts: list[list[dict]],
    states: list[dict],
    expected: set[str],
):
    docker = _fake_docker(volumes, container_mounts, states)

    assert await get_unused_dynamic_sidecar_volumes(docker) == expected


@pytest.fixture
def remove_volume_app(mocker: MockerFixture) -> FastAPI:
    app = FastAPI()
    app.state.settings = SimpleNamespace(AGENT_DOCKER_NODE_ID="node")
    mocker.patch("simcore_service_agent.services.docker_utils.get_instrumentation").return_value = SimpleNamespace(
        agent_metrics=SimpleNamespace(backedup_volumes=Mock(), remove_volumes=Mock())
    )
    return app


@pytest.fixture
def stale_mountpoint_error() -> DockerError:
    return DockerError(
        500,
        "error removing volume path '/docker/volumes/dyv_x/_data': "
        "unlinkat /docker/volumes/dyv_x/_data: device or resource busy",
    )


@pytest.fixture
def fake_volume(mocker: MockerFixture) -> AsyncMock:
    volume = AsyncMock()
    volume.show.return_value = {"Mountpoint": "/docker/volumes/dyv_x/_data"}
    mocker.patch("simcore_service_agent.services.docker_utils.DockerVolume").return_value = volume
    return volume


@pytest.fixture
def run_remove_volume(
    mocker: MockerFixture,
    remove_volume_app: FastAPI,
    fake_volume: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> RunRemoveVolume:
    """Runs remove_volume with the given volume.delete side effects, returning the lazy unmount mock"""

    async def _run(delete_side_effect: list[Exception | None]) -> AsyncMock:
        lazy_unmount = mocker.patch("simcore_service_agent.services.docker_utils._try_lazy_unmount")
        fake_volume.delete.side_effect = delete_side_effect
        caplog.set_level("WARNING")
        caplog.clear()
        await remove_volume(remove_volume_app, _fake_docker(None, []), volume_name="dyv_x", requires_backup=False)
        return lazy_unmount

    return _run


async def test_remove_volume_busy_after_lazy_unmount(
    run_remove_volume: RunRemoveVolume,
    fake_volume: AsyncMock,
    stale_mountpoint_error: DockerError,
    caplog: pytest.LogCaptureFixture,
):
    lazy_unmount = await run_remove_volume([stale_mountpoint_error, stale_mountpoint_error])

    lazy_unmount.assert_awaited_once()
    assert fake_volume.delete.await_count == 2
    assert fake_volume.delete.await_args_list[1].kwargs == {"force": True}
    assert "still busy after lazy unmount" in caplog.text
    assert "umount -l /docker/volumes/dyv_x/_data" in caplog.text
    # a volume still busy after the lazy unmount needs host intervention: exactly one loud, structured error
    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(errors) == 1
    assert "still busy after lazy unmount" in errors[0].getMessage()


async def test_remove_volume_busy_then_success(
    run_remove_volume: RunRemoveVolume,
    fake_volume: AsyncMock,
    stale_mountpoint_error: DockerError,
    caplog: pytest.LogCaptureFixture,
):
    lazy_unmount = await run_remove_volume([stale_mountpoint_error, None])

    lazy_unmount.assert_awaited_once()
    assert fake_volume.delete.await_count == 2
    assert "still busy after lazy unmount" not in caplog.text


async def test_remove_volume_unrelated_error_still_reported(
    run_remove_volume: RunRemoveVolume,
    caplog: pytest.LogCaptureFixture,
):
    await run_remove_volume([DockerError(500, "some unrelated daemon failure")])

    # non-stale-mountpoint errors keep the loud path
    assert [r for r in caplog.records if r.levelname == "ERROR"]


async def test_remove_volume_busy_with_live_binder_refuses_lazy_unmount(
    remove_volume_app: FastAPI,
    fake_volume: AsyncMock,
    stale_mountpoint_error: DockerError,
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
):
    lazy_unmount = mocker.patch("simcore_service_agent.services.docker_utils._try_lazy_unmount")
    fake_volume.delete.side_effect = stale_mountpoint_error
    docker = _fake_docker(
        [_dyv_volume("dyv_x")],
        [[{"Type": "bind", "Source": "/docker/volumes/dyv_x/_data"}]],
        [_RUNNING],
    )

    caplog.clear()
    with caplog.at_level("WARNING"):
        await remove_volume(remove_volume_app, docker, volume_name="dyv_x", requires_backup=False)

    lazy_unmount.assert_not_awaited()
    fake_volume.delete.assert_awaited_once()
    assert "held by a running container before lazy unmount" in caplog.text


async def test_remove_volume_binder_appears_after_lazy_unmount_refuses_force_delete(
    remove_volume_app: FastAPI,
    fake_volume: AsyncMock,
    stale_mountpoint_error: DockerError,
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
):
    lazy_unmount = mocker.patch("simcore_service_agent.services.docker_utils._try_lazy_unmount")
    probe = mocker.patch(
        "simcore_service_agent.services.docker_utils._volume_mountpoint_is_held_by_running_container",
        new_callable=AsyncMock,
        side_effect=[False, True],
    )
    fake_volume.delete.side_effect = stale_mountpoint_error

    caplog.clear()
    with caplog.at_level("WARNING"):
        await remove_volume(remove_volume_app, _fake_docker(None, []), volume_name="dyv_x", requires_backup=False)

    lazy_unmount.assert_awaited_once()
    assert probe.await_count == 2
    fake_volume.delete.assert_awaited_once()  # no force retry once a live binder appeared
    assert "held by a running container after lazy unmount" in caplog.text


async def test_remove_volume_unrelated_error_on_force_retry_is_reported(
    run_remove_volume: RunRemoveVolume,
    fake_volume: AsyncMock,
    stale_mountpoint_error: DockerError,
    caplog: pytest.LogCaptureFixture,
):
    await run_remove_volume([stale_mountpoint_error, DockerError(500, "daemon went away")])

    assert fake_volume.delete.await_count == 2
    assert "still busy after lazy unmount" not in caplog.text
    assert [r for r in caplog.records if r.levelname == "ERROR"]


async def test_remove_volume_without_mountpoint_skips_lazy_unmount(
    run_remove_volume: RunRemoveVolume,
    fake_volume: AsyncMock,
    stale_mountpoint_error: DockerError,
):
    fake_volume.show.return_value = {}

    lazy_unmount = await run_remove_volume([stale_mountpoint_error, None])

    lazy_unmount.assert_not_awaited()
    assert fake_volume.delete.await_count == 2
    assert fake_volume.delete.await_args_list[1].kwargs == {"force": True}


async def test_remove_volume_deleted_during_stale_handling_reports_not_found(
    remove_volume_app: FastAPI,
    fake_volume: AsyncMock,
    stale_mountpoint_error: DockerError,
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
):
    lazy_unmount = mocker.patch("simcore_service_agent.services.docker_utils._try_lazy_unmount")
    fake_volume.delete.side_effect = stale_mountpoint_error
    fake_volume.show.side_effect = DockerError(404, "volume no such volume")

    caplog.clear()
    with caplog.at_level("INFO"):
        await remove_volume(remove_volume_app, _fake_docker(None, []), volume_name="dyv_x", requires_backup=False)

    lazy_unmount.assert_not_awaited()
    fake_volume.delete.assert_awaited_once()
    assert "Volume not found 'dyv_x'" in caplog.text
