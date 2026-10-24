from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pytest_simcore.docker_swarm import (
    _get_swarm_cluster_id,
    _list_owned_migration_services,
    _swarm_membership_token,
)


@dataclass
class _FakeService:
    name: str


@dataclass
class _FakeServices:
    services: list[_FakeService]

    def list(self) -> list[_FakeService]:
        return self.services


@dataclass
class _FakeClient:
    services: _FakeServices


@dataclass
class _FakeInfoClient:
    _info: dict[str, Any]

    def info(self) -> dict[str, Any]:
        return self._info


def _fake_client(service_names: list[str]) -> _FakeClient:
    return _FakeClient(_FakeServices([_FakeService(name) for name in service_names]))


def test_migration_services_are_selected_by_exact_name():
    # a substring match on "migration" would also select services of other stacks
    core_stack = "pytest-s1-core"

    own_services = [f"{core_stack}_{key}" for key in ("postgres", "redis", "migration")]
    # a co-tenant checkout in another slot has its own migration service, which must
    # be left alone
    co_tenant = "pytest-s2-core_migration"
    client = _fake_client([*own_services, co_tenant])

    owned = _list_owned_migration_services(client, core_stack)  # type: ignore[arg-type]

    assert [str(service.name) for service in owned] == [f"{core_stack}_migration"]


def test_swarm_membership_token_is_shared_by_controller_and_workers(tmp_path: Path):
    # pytest layout: <...>/pytest-of-<user>/pytest-<N>[/popen-gwX]; the basetemp of a plain
    # session or of the xdist controller IS the run dir, a worker's basetemp is a subdir of it
    run_dir = tmp_path / "pytest-of-dev" / "pytest-7"

    session_token = _swarm_membership_token(run_dir, xdist_worker=False)
    controller_token = _swarm_membership_token(run_dir, xdist_worker=False)
    worker_token = _swarm_membership_token(run_dir / "popen-gw3", xdist_worker=True)

    # the whole run registers under ONE token, else workers and controller could not
    # join/leave the same membership set
    assert session_token == controller_token == worker_token


def test_swarm_membership_token_is_unique_per_run_and_user(tmp_path: Path):
    token = _swarm_membership_token(tmp_path / "pytest-of-dev" / "pytest-7", xdist_worker=False)

    # concurrent runs of one user get distinct pytest-<N> counters
    other_run = _swarm_membership_token(tmp_path / "pytest-of-dev" / "pytest-8", xdist_worker=False)
    assert other_run != token

    # different users share neither counters nor tokens (parent dir is per user)
    other_user = _swarm_membership_token(tmp_path / "pytest-of-other" / "pytest-7", xdist_worker=False)
    assert other_user != token


def test_swarm_membership_token_is_unique_for_distinct_basetemps_sharing_their_tail(tmp_path: Path):
    # regression: tokens derived from only the last path components collided for runs given
    # explicit --basetemp dirs like these; the second run then overwrote the first's member
    # file and either run finishing removed the sole token, leaving the swarm mid-run
    token_a = _swarm_membership_token(tmp_path / "worktrees" / "a" / ".pytest" / "tmp", xdist_worker=False)
    token_b = _swarm_membership_token(tmp_path / "worktrees" / "b" / ".pytest" / "tmp", xdist_worker=False)

    assert token_a != token_b


def test_swarm_cluster_id_is_read_from_the_api_shaped_info_response():
    # regression: the docker /info response nests the swarm ID as Swarm.Cluster.ID; reading a
    # flat Swarm.ClusterID always yielded "" (the field does not exist), silently disabling the
    # lineage cluster-ID check. the fake-swarm unit tests cannot catch this as they inject their
    # own id callable, so pin the lookup itself against the real API shape
    active = _FakeInfoClient({"Swarm": {"LocalNodeState": "active", "Cluster": {"ID": "swarm-1"}}})
    assert _get_swarm_cluster_id(active) == "swarm-1"  # type: ignore[arg-type]


def test_swarm_cluster_id_is_empty_when_out_of_swarm_mode():
    # out of swarm mode the daemon reports no Cluster at all
    inactive = _FakeInfoClient({"Swarm": {"LocalNodeState": "inactive"}})
    assert _get_swarm_cluster_id(inactive) == ""  # type: ignore[arg-type]
