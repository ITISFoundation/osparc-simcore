# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import logging
import os
from pprint import pformat, pprint

import pytest
from yarl import URL

from simcore_service_director_v2.core.settings import AppSettings, BootModeEnum


@pytest.fixture
def fake_environs(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "production_postgres")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")

    monkeypatch.setenv("EXTRA_HOSTS_SUFFIX", "foo")

    monkeypatch.setenv("SC_BOOT_MODE", "production")

    yield os.environ


def test_min_environ_for_app_settings(fake_environs):
    app_settings: AppSettings = AppSettings.create_default()

    pprint(app_settings.dict())

    assert app_settings.boot_mode == BootModeEnum.PRODUCTION
    assert app_settings.loglevel == logging.DEBUG
    assert app_settings.extra_hosts_suffix == "foo"

    assert app_settings.postgres.dsn == URL(
        "postgresql://test:test@production_postgres:5432/test"
    )

    # should not raise
    services_default_envs = {
        "POSTGRES_ENDPOINT": str(app_settings.postgres.dsn),
        "POSTGRES_USER": app_settings.postgres.user,
        "POSTGRES_PASSWORD": app_settings.postgres.password,
        "POSTGRES_DB": app_settings.postgres.db,
        "STORAGE_ENDPOINT": app_settings.storage_endpoint,
    }

    assert all(services_default_envs.values()), "Some values are empty: %s" % pformat(
        services_default_envs
    )
