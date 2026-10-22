# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Annotated, Final
from unittest import mock

import docker.client
import pytest
from annotated_types import doc
from pytest_simcore.helpers.dev_slot import (
    DevSlotMismatchError,
    find_foreign_port_publishers,
    lease_checkout_slot,
    load_dev_slot_module,
)
from pytest_simcore.helpers.stack_names import MAX_STACK_NAME_LEN

_DOCKER_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_COMPOSE_HOST_PORT: Final[re.Pattern[str]] = re.compile(r"\$\{(?P<name>[A-Z0-9_]+_HOST_PORT):-(?P<port>\d+)\}")
_KNOWN_LEGACY_OVERLAP: Final[
    Annotated[frozenset[str], doc("Both already used host port 8080 before slots existed")]
] = frozenset({"QX_SERVE_HOST_PORT", "TRAEFIK_DASHBOARD_HOST_PORT"})


@pytest.fixture
def dev_slot(osparc_simcore_root_dir: Path) -> ModuleType:
    return load_dev_slot_module(osparc_simcore_root_dir)


class _FakeDockerNetworks:
    """Fake `docker network` CLI"""

    def __init__(self) -> None:
        self.markers: dict[str, str] = {}
        self.before_create: Callable[[str], None] | None = None

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        match args:
            case ["network", "ls", *_]:
                stdout = "".join(f"{name}\t{checkout}\n" for name, checkout in self.markers.items())
                return subprocess.CompletedProcess(args, 0, stdout, "")
            case ["network", "create", "--config-only", "--label", label, name]:
                if self.before_create:
                    self.before_create(name)
                if name in self.markers:
                    return subprocess.CompletedProcess(
                        args, 1, "", f"Error response from daemon: network with name {name} already exists"
                    )
                self.markers[name] = label.partition("=")[2]
                return subprocess.CompletedProcess(args, 0, "id\n", "")
            case ["network", "rm", name]:
                self.markers.pop(name, None)
                return subprocess.CompletedProcess(args, 0, f"{name}\n", "")
        msg = f"unexpected docker call {args}"
        raise AssertionError(msg)


@pytest.fixture
def fake_docker() -> _FakeDockerNetworks:
    return _FakeDockerNetworks()


@pytest.fixture
def make_checkout(tmp_path: Path) -> Callable[[str], Path]:
    def _make(name: str) -> Path:
        checkout = tmp_path / name
        checkout.mkdir()
        return checkout

    return _make


def test_slot_zero_keeps_the_legacy_names_and_ports(dev_slot: ModuleType):
    env = dev_slot.derive_env(0)

    assert env["SWARM_STACK_NAME"] == "master-simcore"
    assert env["SWARM_OPS_STACK_NAME"] == "ops"
    assert env["SWARM_VENDORS_STACK_NAME"] == "vendors"
    assert env["TRAEFIK_SIMCORE_ZONE"] == "internal_simcore_stack"
    assert env["LOCAL_IMAGE_TAG_SUFFIX"] == ""
    assert env["TRAEFIK_HTTP_HOST_PORT"] == "9081"
    assert env["S3_HOST_PORT"] == "9001"
    assert env["WEBSERVER_DEBUG_HOST_PORT"] == "3001"


def test_other_slots_get_short_numbered_names_and_shifted_ports(dev_slot: ModuleType):
    env = dev_slot.derive_env(3)

    assert env["OSPARC_DEV_SLOT"] == "3"
    assert env["SWARM_STACK_NAME"] == "simcore-s3"
    assert env["SWARM_OPS_STACK_NAME"] == "ops-s3"
    assert env["SWARM_VENDORS_STACK_NAME"] == "vendors-s3"
    assert env["TRAEFIK_SIMCORE_ZONE"] == "internal_simcore_stack_s3"
    assert env["LOCAL_IMAGE_TAG_SUFFIX"] == "-s3"
    assert env["TRAEFIK_HTTP_HOST_PORT"] == "9381"
    assert env["S3_HOST_PORT"] == "9301"
    assert dev_slot.pytest_stack_names(3) == ("pytest-s3-core", "pytest-s3-ops")


def test_host_ports_never_collide_across_slots(dev_slot: ModuleType):
    owners: dict[int, tuple[int, str]] = {}
    for slot in range(dev_slot.SLOT_COUNT):
        for name, port in dev_slot.host_ports(slot).items():
            assert 1024 < port <= 65535, (slot, name, port)
            if port in owners:
                other = owners[port]
                assert other[0] == slot, f"slot {slot} {name} and slot {other[0]} {other[1]} share port {port}"
                assert {name, other[1]} == _KNOWN_LEGACY_OVERLAP, f"{name} and {other[1]} share port {port}"
            owners[port] = (slot, name)


def test_stack_names_fit_the_dns_label_budget_and_are_unique(dev_slot: ModuleType):
    names = [
        name
        for slot in range(dev_slot.SLOT_COUNT)
        for name in (*dev_slot.stack_names(slot).values(), *dev_slot.pytest_stack_names(slot))
    ]
    assert len(set(names)) == len(names)
    for name in names:
        assert len(name) <= MAX_STACK_NAME_LEN, name
        assert _DOCKER_NAME_PATTERN.match(name), name


@pytest.mark.parametrize(
    "compose_path",
    [
        "services/docker-compose.local.yml",
        "services/docker-compose-ops.yml",
        "services/docker-compose-ops-ci.yml",
        "services/static-webserver/client/tools/docker-compose.yml",
    ],
)
def test_compose_host_ports_default_to_their_slot_zero_port(
    dev_slot: ModuleType, osparc_simcore_root_dir: Path, compose_path: str
):
    content = (osparc_simcore_root_dir / compose_path).read_text()

    defaults = {match["name"]: int(match["port"]) for match in _COMPOSE_HOST_PORT.finditer(content)}

    assert defaults
    assert {name: dev_slot.LEGACY_HOST_PORTS.get(name) for name in defaults} == defaults


def test_every_slot_host_port_is_published_by_a_compose_file(dev_slot: ModuleType, osparc_simcore_root_dir: Path):
    compose_files = [
        *osparc_simcore_root_dir.glob("services/docker-compose*.yml"),
        osparc_simcore_root_dir / "services/static-webserver/client/tools/docker-compose.yml",
    ]
    used = {match["name"] for path in compose_files for match in _COMPOSE_HOST_PORT.finditer(path.read_text())}

    assert set(dev_slot.LEGACY_HOST_PORTS) == used


def test_first_checkout_gets_slot_zero_and_keeps_it(
    dev_slot: ModuleType, fake_docker: _FakeDockerNetworks, make_checkout: Callable[[str], Path]
):
    main, worktree = make_checkout("main"), make_checkout("worktree")

    assert dev_slot.lease(main, run=fake_docker) == 0
    assert dev_slot.lease(worktree, run=fake_docker) == 1
    assert dev_slot.lease(main, run=fake_docker) == 0
    assert dev_slot.lease(worktree, run=fake_docker) == 1
    assert dev_slot.list_markers(fake_docker) == {0: f"{main.resolve()}", 1: f"{worktree.resolve()}"}


def test_lease_prefers_the_cached_slot_when_free(
    dev_slot: ModuleType, fake_docker: _FakeDockerNetworks, make_checkout: Callable[[str], Path]
):
    assert dev_slot.lease(make_checkout("worktree"), preferred=4, run=fake_docker) == 4


def test_requested_slot_moves_the_checkout(
    dev_slot: ModuleType, fake_docker: _FakeDockerNetworks, make_checkout: Callable[[str], Path]
):
    main, worktree = make_checkout("main"), make_checkout("worktree")
    assert dev_slot.lease(main, run=fake_docker) == 0

    assert dev_slot.lease(main, requested=5, run=fake_docker) == 5
    assert dev_slot.list_markers(fake_docker) == {5: f"{main.resolve()}"}

    with pytest.raises(dev_slot.SlotTakenError):
        dev_slot.lease(worktree, requested=5, run=fake_docker)


def test_slots_of_deleted_checkouts_are_reclaimed(
    dev_slot: ModuleType, fake_docker: _FakeDockerNetworks, make_checkout: Callable[[str], Path]
):
    deleted = make_checkout("deleted-worktree")
    assert dev_slot.lease(deleted, run=fake_docker) == 0
    deleted.rmdir()

    assert dev_slot.lease(make_checkout("new-worktree"), run=fake_docker) == 0


def test_lease_fails_when_every_slot_is_held(
    dev_slot: ModuleType, fake_docker: _FakeDockerNetworks, make_checkout: Callable[[str], Path]
):
    for index in range(dev_slot.SLOT_COUNT):
        dev_slot.lease(make_checkout(f"checkout-{index}"), run=fake_docker)

    with pytest.raises(dev_slot.NoFreeSlotError):
        dev_slot.lease(make_checkout("one-too-many"), run=fake_docker)


def test_concurrent_leases_of_one_checkout_share_its_slot(
    dev_slot: ModuleType, fake_docker: _FakeDockerNetworks, make_checkout: Callable[[str], Path]
):
    checkout = make_checkout("main")

    def _concurrent_same_checkout_wins(name: str) -> None:
        fake_docker.before_create = None
        fake_docker.markers[name] = f"{checkout.resolve()}"

    fake_docker.before_create = _concurrent_same_checkout_wins

    assert dev_slot.lease(checkout, run=fake_docker) == 0
    assert dev_slot.list_markers(fake_docker) == {0: f"{checkout.resolve()}"}


def test_concurrent_lease_of_another_checkout_moves_on(
    dev_slot: ModuleType, fake_docker: _FakeDockerNetworks, make_checkout: Callable[[str], Path]
):
    other = make_checkout("other")

    def _concurrent_other_checkout_wins(name: str) -> None:
        fake_docker.before_create = None
        fake_docker.markers[name] = f"{other.resolve()}"

    fake_docker.before_create = _concurrent_other_checkout_wins

    assert dev_slot.lease(make_checkout("main"), run=fake_docker) == 1


@pytest.mark.parametrize(
    "content,expected",
    [
        ("FOO=1\n", None),
        ("OSPARC_DEV_SLOT=3\nFOO=1\n", 3),
        ("OSPARC_DEV_SLOT=0\nFOO=1\nOSPARC_DEV_SLOT=7\n", 7),
        ("OSPARC_DEV_SLOT=99\n", None),
        ("OSPARC_DEV_SLOT=abc\n", None),
    ],
    ids=["missing", "set", "last-wins", "out-of-range", "not-a-number"],
)
def test_read_cached_slot(dev_slot: ModuleType, tmp_path: Path, content: str, expected: int | None):
    env_file = tmp_path / "env"
    env_file.write_text(content)

    assert dev_slot.read_cached_slot(env_file) == expected


def test_write_cached_slot_replaces_the_cached_value_in_place(dev_slot: ModuleType, tmp_path: Path):
    env_file = tmp_path / "env"
    env_file.write_text("FOO=1\nOSPARC_DEV_SLOT=0\nBAR=2\n")

    dev_slot.write_cached_slot(env_file, 6)

    assert env_file.read_text() == "FOO=1\nOSPARC_DEV_SLOT=6\nBAR=2\n"


def test_write_cached_slot_adds_a_missing_value(dev_slot: ModuleType, tmp_path: Path):
    env_file = tmp_path / "env"
    env_file.write_text("FOO=1\n")

    dev_slot.write_cached_slot(env_file, 2)

    assert dev_slot.read_cached_slot(env_file) == 2
    assert "FOO=1\n" in env_file.read_text()


def test_shift_ports_only_moves_slot_host_ports(dev_slot: ModuleType):
    launch = '{"connect": {"port": 3001, "host": "127.0.0.1"}, "other": {"port": 5678}}'

    shifted = '{"connect": {"port": 3201, "host": "127.0.0.1"}, "other": {"port": 5678}}'
    assert dev_slot.shift_ports(launch, 2) == shifted
    assert dev_slot.shift_ports(launch, 0) == launch


def test_cli_env_make_format_is_one_token_per_variable(dev_slot: ModuleType, capsys: pytest.CaptureFixture[str]):
    assert dev_slot.main(["env", "--slot", "1", "--format", "make"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert "SWARM_STACK_NAME?=simcore-s1" in lines
    assert "LOCAL_IMAGE_TAG_SUFFIX?=-s1" in lines
    assert all(" " not in line for line in lines)


def test_lease_checkout_slot_rejects_a_moved_slot(
    osparc_simcore_root_dir: Path,
    dev_slot: ModuleType,
    fake_docker: _FakeDockerNetworks,
    make_checkout: Callable[[str], Path],
    monkeypatch: pytest.MonkeyPatch,
):
    checkout = make_checkout("worktree")
    (checkout / "scripts").mkdir()
    (checkout / "scripts" / "dev_slot.py").write_text((osparc_simcore_root_dir / "scripts" / "dev_slot.py").read_text())
    (checkout / ".env").write_text("OSPARC_DEV_SLOT=0\n")
    # another checkout took slot 0 meanwhile
    dev_slot.lease(make_checkout("other"), run=fake_docker)

    with pytest.raises(DevSlotMismatchError):
        lease_checkout_slot(checkout, accept_moved_slot=False, run_docker=fake_docker)

    assert lease_checkout_slot(checkout, accept_moved_slot=True, run_docker=fake_docker) == 1


def _fake_service(name: str, stack: str, published: list[int]) -> mock.Mock:
    service = mock.Mock()
    service.name = name
    service.attrs = {
        "Spec": {"Labels": {"com.docker.stack.namespace": stack}},
        "Endpoint": {"Ports": [{"TargetPort": 1, "PublishedPort": port} for port in published]},
    }
    return service


def _fake_container(name: str, host_ports: list[int]) -> mock.Mock:
    container = mock.Mock()
    container.name = name
    container.labels = {}
    container.attrs = {
        "NetworkSettings": {"Ports": {"8080/tcp": [{"HostIp": "0.0.0.0", "HostPort": f"{p}"} for p in host_ports]}}  # noqa: S104
    }
    return container


def test_find_foreign_port_publishers_ignores_own_stacks():
    client = mock.create_autospec(docker.client.DockerClient, instance=True)
    client.services.list.return_value = [
        _fake_service("pytest-s0-core_traefik", "pytest-s0-core", [9081]),
        _fake_service("master-simcore_traefik", "master-simcore", [9081, 10081]),
        _fake_service("simcore-s1_traefik", "simcore-s1", [9181]),
    ]
    client.containers.list.return_value = [_fake_container("qooxdoo-kit", [8080])]

    publishers = find_foreign_port_publishers(client, [9081, 10081, 8080, 9001], ["pytest-s0-core", "pytest-s0-ops"])

    assert publishers == {
        9081: "service master-simcore_traefik",
        10081: "service master-simcore_traefik",
        8080: "container qooxdoo-kit",
    }
