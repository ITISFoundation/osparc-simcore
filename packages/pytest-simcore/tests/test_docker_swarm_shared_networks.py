# pylint: disable=protected-access

from pathlib import Path
from unittest import mock

import docker
import docker.errors
import pytest
from docker.errors import APIError
from pytest_simcore.docker_swarm import (
    _CREATED_STACK_NETWORKS_MARKER_NAME,
    _get_or_create_network,
    _record_created_network_for_shared_cleanup,
    _take_created_networks_for_shared_cleanup,
)


def _api_error(status_code: int | None) -> APIError:
    response = mock.Mock()
    response.status_code = status_code
    return APIError("boom", response=response)


def test_take_created_networks_returns_empty_when_nothing_recorded(tmp_path: Path):
    assert _take_created_networks_for_shared_cleanup(tmp_path) == []


def test_record_then_take_returns_all_created_networks_once(tmp_path: Path):
    _record_created_network_for_shared_cleanup(tmp_path, "net_a")
    _record_created_network_for_shared_cleanup(tmp_path, "net_b")
    _record_created_network_for_shared_cleanup(tmp_path, "net_a")  # same name recorded twice is fine

    assert _take_created_networks_for_shared_cleanup(tmp_path) == ["net_a", "net_b", "net_a"]

    # taking clears the marker: a second take finds nothing (networks removed exactly once)
    assert _take_created_networks_for_shared_cleanup(tmp_path) == []
    assert not (tmp_path / _CREATED_STACK_NETWORKS_MARKER_NAME).exists()


def test_get_or_create_network_attaches_to_existing_network_without_creating():
    existing = mock.Mock()
    client = mock.Mock()
    client.networks.get.return_value = existing

    network, created_new = _get_or_create_network(client, "test-network")

    assert network is existing
    assert created_new is False
    client.networks.create.assert_not_called()


def test_get_or_create_network_recovers_from_409_create_race():
    # both workers observe NotFound and race to create: the loser gets a 409 Conflict and
    # must fetch what the winner created (first `get` NotFound, second one returns the network)
    winner_network = mock.Mock()
    client = mock.Mock()
    client.networks.get.side_effect = [docker.errors.NotFound("not yet"), winner_network]
    client.networks.create.side_effect = _api_error(409)

    network, created_new = _get_or_create_network(client, "test-network")

    assert network is winner_network
    assert created_new is False


def test_get_or_create_network_reraises_non_409_api_errors():
    client = mock.Mock()
    client.networks.get.side_effect = docker.errors.NotFound("nope")
    client.networks.create.side_effect = _api_error(500)

    with pytest.raises(APIError):
        _get_or_create_network(client, "test-network")


def test_get_or_create_network_reraises_api_errors_without_response():
    client = mock.Mock()
    client.networks.get.side_effect = docker.errors.NotFound("nope")
    client.networks.create.side_effect = APIError("connection reset", response=None)

    with pytest.raises(APIError):
        _get_or_create_network(client, "test-network")
