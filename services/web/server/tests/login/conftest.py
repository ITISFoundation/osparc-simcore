# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
import sys
import yaml
from pathlib import Path

from simcore_service_webserver.application import create_app
import simcore_service_webserver.utils

@pytest.fixture(scope="session")
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope="session")
def app_cfg(here, aiohttp_unused_port):
    cfg_path = here / "config.yaml"

    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)

    #FIXME: server_kwargs={'port': aiohttp_unused_port(), 'host': 'localhost'}
    return cfg

@pytest.fixture
def server(loop, aiohttp_server, app_cfg, monkeypatch):
    app = create_app(app_cfg)
    path_mail(monkeypatch)
    server = loop.run_until_complete(aiohttp_server(app,
        port =app_cfg["main"]["port"],
        host =app_cfg["main"]["host"]))
    return server


@pytest.fixture
def client(loop, aiohttp_client, server):
    client = loop.run_until_complete(aiohttp_client(server))
    return client


# helpers ----
def path_mail(monkeypatch):
    async def send_mail(*args):
        print('=== EMAIL TO: {}\n=== SUBJECT: {}\n=== BODY:\n{}'.format(*args))

    monkeypatch.setattr(simcore_service_webserver.utils, 'send_mail', send_mail)
