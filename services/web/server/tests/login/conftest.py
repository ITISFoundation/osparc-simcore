# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import sys
from pathlib import Path

import pytest
import trafaret_config
import yaml

import simcore_service_webserver.utils
from simcore_service_webserver.settings import CONFIG_SCHEMA
from simcore_service_webserver.application import create_application


@pytest.fixture(scope="session")
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope="session")
def app_cfg(here):
    cfg_path = here / "config.yaml"
    assert cfg_path.exists()

    # validates and fills all defaults/optional entries that normal load would not do
    cfg_dict = trafaret_config.read_and_validate(cfg_path, CONFIG_SCHEMA)
    return cfg_dict

@pytest.fixture
def server(loop, aiohttp_server, app_cfg, monkeypatch, aiohttp_unused_port):
    app_cfg["main"]["port"] = aiohttp_unused_port()
    host, port = tuple(app_cfg["main"][k] for k in ("host", "port"))

    app = create_application(app_cfg)
    path_mail(monkeypatch)
    server = loop.run_until_complete(aiohttp_server(app, port=port, host=host))
    return server


@pytest.fixture
def client(loop, aiohttp_client, server):
    client = loop.run_until_complete(aiohttp_client(server))
    return client


# helpers ----
def path_mail(monkeypatch):
    async def send_mail(*args):
        print('=== EMAIL TO: {}\n=== SUBJECT: {}\n=== BODY:\n{}'.format(*args))

    monkeypatch.setattr(simcore_service_webserver.login.utils, 'send_mail', send_mail)
