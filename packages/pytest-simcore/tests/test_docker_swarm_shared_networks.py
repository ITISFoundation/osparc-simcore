# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest import mock

import docker
import docker.errors
import pytest
from docker.errors import APIError
from pytest_simcore import docker_swarm
from pytest_simcore.docker_swarm import _get_or_create_network, _remove_network_when_free


def _api_error(status_code: int | None) -> APIError:
    response = mock.Mock()
    response.status_code = status_code
    return APIError("boom", response=response)


@pytest.fixture
def fast_retrying(monkeypatch: pytest.MonkeyPatch):
    """makes the retry loops inside docker_swarm neither sleep nor run for minutes:
    waits are instant and the time-based stop gives up after a few attempts
    """
    monkeypatch.setattr(docker_swarm, "wait_fixed", lambda *_a, **_kw: lambda *_a2, **_kw2: 0)

    def _stop_after(num_attempts: int):
        remaining = iter(range(num_attempts + 1))

        def _stop(*_args, **_kwargs):
            return next(remaining, num_attempts) >= num_attempts

        return _stop

    monkeypatch.setattr(docker_swarm, "stop_after_delay", _stop_after)


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


def test_remove_network_when_free_retries_while_endpoints_attached(fast_retrying):
    # swarm endpoint draining after `docker stack remove` is asynchronous: removal must retry
    # while the daemon reports active endpoints and stop as soon as it succeeds
    network = mock.Mock()
    network.remove.side_effect = [
        _api_error(403),  # "network has active endpoints"
        _api_error(403),
        None,
    ]
    client = mock.Mock()
    client.networks.get.return_value = network

    _remove_network_when_free(client, "test-network")

    assert network.remove.call_count == 3


def test_remove_network_when_free_skips_already_gone_network(fast_retrying):
    client = mock.Mock()
    client.networks.get.side_effect = docker.errors.NotFound("already gone")

    _remove_network_when_free(client, "test-network")  # must not raise


def test_remove_network_when_free_reraises_persistent_api_errors(fast_retrying):
    # a network stuck with endpoints from a foreign session must surface, not hang forever
    network = mock.Mock()
    network.remove.side_effect = _api_error(403)
    client = mock.Mock()
    client.networks.get.return_value = network

    with pytest.raises(APIError):
        _remove_network_when_free(client, "test-network")

    assert network.remove.call_count > 1  # it retried before giving up
