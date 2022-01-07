# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
from copy import deepcopy
from typing import Any, Dict

import pytest
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.log import setup_logging

# HELPERS


# FIXTURES


@pytest.fixture
def user_role() -> UserRole:
    # TODO: user rights still not in place
    return UserRole.TESTER


@pytest.fixture
def app_cfg(default_app_cfg, aiohttp_unused_port, monkeypatch) -> Dict[str, Any]:
    """App's configuration used for every test in this module

    NOTE: Overrides services/web/server/tests/unit/with_dbs/conftest.py::app_cfg to influence app setup
    """
    cfg = deepcopy(default_app_cfg)

    monkeypatch.setenv("WEBSERVER_DEV_FEATURES_ENABLED", "1")

    cfg["main"]["port"] = aiohttp_unused_port()
    cfg["main"]["studies_access_enabled"] = True

    exclude = {
        "activity",
        "catalog",
        "clusters",
        "computation",
        "diagnostics",
        "director",
        "groups",
        "publications",
        "resource_manager",
        "smtp",
        "socketio",
        "storage",
        "studies_access",
        "studies_dispatcher",
        "tags",
        "tracing",
    }
    include = {
        "db",
        "login",
        "products",
        "projects",
        "version_control",
        "rest",
        "users",
        # "meta",  # MODULE UNDER TEST
    }

    assert include.intersection(exclude) == set()

    for section in include:
        cfg[section]["enabled"] = True
    for section in exclude:
        cfg[section]["enabled"] = False

    # NOTE: To see logs, use pytest -s --log-cli-level=DEBUG
    setup_logging(level=logging.DEBUG)

    # Enforces smallest GC in the background task
    cfg["resource_manager"]["garbage_collection_interval_seconds"] = 1

    return cfg
