# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from aiohttp.test_utils import TestClient
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_webserver.invitations import setup_invitations
from simcore_service_webserver.invitations_settings import InvitationsSettings


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: MonkeyPatch):
    assert InvitationsSettings.create_from_envs()

    return app_environment


def test_setup_invitations(client: TestClient):
    setup_invitations(app=client.app)


# create fake invitation service


# valid invitation

# invalid invitation

# confirmation-type of invitations
