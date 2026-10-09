# pylint: disable=protected-access

from pathlib import Path

from pytest_simcore.docker_swarm import (
    _CREATED_STACK_NETWORKS_MARKER_NAME,
    _record_created_network_for_shared_cleanup,
    _take_created_networks_for_shared_cleanup,
)


def test_take_created_networks_returns_empty_when_nothing_recorded(tmp_path: Path):
    assert _take_created_networks_for_shared_cleanup(tmp_path) == []


def test_record_then_take_returns_all_created_networks_once(tmp_path: Path) -> None:
    _record_created_network_for_shared_cleanup(tmp_path, "net_a")
    _record_created_network_for_shared_cleanup(tmp_path, "net_b")
    _record_created_network_for_shared_cleanup(tmp_path, "net_a")  # same name recorded twice is fine

    assert _take_created_networks_for_shared_cleanup(tmp_path) == ["net_a", "net_b", "net_a"]

    # taking clears the marker: a second take finds nothing (networks removed exactly once)
    assert _take_created_networks_for_shared_cleanup(tmp_path) == []
    assert not (tmp_path / _CREATED_STACK_NETWORKS_MARKER_NAME).exists()
