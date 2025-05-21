# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import json
import re
from collections.abc import Callable

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from servicelib.aiohttp.application import create_safe_application
from simcore_postgres_database.models.products import products
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.products.plugin import setup_products
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.statics._constants import (
    APP_FRONTEND_CACHED_STATICS_JSON_KEY,
)
from simcore_service_webserver.statics._events import (
    _get_release_notes_vtag,
    create_and_cache_statics_json,
)
from simcore_service_webserver.statics.plugin import setup_statics


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, vcs_release_tag: str
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch, envs={"SIMCORE_VCS_RELEASE_TAG": vcs_release_tag}
    )


@pytest.fixture
def mock_static_webserver(aioresponses_mocker: aioresponses) -> None:
    aioresponses_mocker.get(
        re.compile(r"http://static-webserver:8000/.*"),
        status=status.HTTP_200_OK,
        repeat=True,
    )


@pytest.fixture
async def client(
    mock_static_webserver: None,
    app_environment: EnvVarsDict,
    aiohttp_client: Callable,
    postgres_db: sa.engine.Engine,
) -> TestClient:
    app = create_safe_application()

    settings = setup_settings(app)
    assert settings.WEBSERVER_STATICWEB
    setup_rest(app)
    setup_db(app)
    setup_products(app)
    assert setup_statics(app)

    return await aiohttp_client(app, server_kwargs={"host": "localhost"})


@pytest.mark.parametrize(
    "vcs_release_tag, expected_vcs_url",
    [
        pytest.param(
            "latest",
            "https://github.com/ITISFoundation/osparc-simcore/commits/master/",
            id="master",
        ),
        pytest.param(
            "staging_TomBombadil1",
            "https://github.com/ITISFoundation/osparc-simcore/releases/tag/staging_TomBombadil1",
            id="staging",
        ),
        pytest.param(
            "v1.75.0",
            "https://github.com/ITISFoundation/osparc-simcore/releases/tag/v1.75.0",
            id="production",
        ),
    ],
)
async def test_create_and_cache_statics_json_legacy_vcs_implementation(
    client: TestClient, expected_vcs_url: str, vcs_release_tag: str
):
    assert client.app
    await create_and_cache_statics_json(client.app)
    for product_data in client.app[APP_FRONTEND_CACHED_STATICS_JSON_KEY].values():
        product_dict = json.loads(product_data)
        assert product_dict.get("vcsReleaseTag") == vcs_release_tag
        assert product_dict.get("vcsReleaseUrl") == expected_vcs_url


@pytest.fixture
def mock_product_vendor(postgres_db: sa.engine.Engine, template_url: str) -> None:
    with postgres_db.connect() as con:
        con.execute(
            products.update()
            .where(products.c.name == "osparc")
            .values(vendor={"release_notes_url_template": template_url})
        )


@pytest.mark.parametrize(
    "vcs_release_tag, template_url, expected_vcs_url",
    [
        pytest.param(
            "v1.75.0",
            "https://example.com/releases/some_target_{vtag}.md",
            "https://example.com/releases/some_target_v1.75.0.md",
            id="production_replacement_first_exmample",
        ),
        pytest.param(
            "v2.1.0",
            "https://github.com/owner/repo/releases/{vtag}.md",
            "https://github.com/owner/repo/releases/v2.1.0.md",
            id="production_replacement_second_exmample",
        ),
        pytest.param(
            "latest",
            "https://github.com/owner/repo/releases/{vtag}.md",
            "https://github.com/ITISFoundation/osparc-simcore/commits/master/",
            id="master_with_template_in_place",
        ),
        pytest.param(
            "staging_TomBombadil1",
            "https://github.com/owner/repo/releases/{vtag}.md",
            "https://github.com/ITISFoundation/osparc-simcore/releases/tag/staging_TomBombadil1",
            id="staging_with_template_in_place",
        ),
        pytest.param(
            "v1.75.0",
            "https://example.com/no_vtag.md",
            "https://example.com/no_vtag.md",
            id="vtag_not_repalced_if_missing",
        ),
    ],
)
async def test_create_and_cache_statics_json_vendor_vcs_overwrite(
    mock_product_vendor: None,
    client: TestClient,
    expected_vcs_url: str,
    vcs_release_tag: str,
):
    assert client.app
    await create_and_cache_statics_json(client.app)
    for product_data in client.app[APP_FRONTEND_CACHED_STATICS_JSON_KEY].values():
        product_dict = json.loads(product_data)
        assert product_dict.get("vcsReleaseTag") == vcs_release_tag
        assert product_dict.get("vcsReleaseUrl") == expected_vcs_url


@pytest.mark.parametrize(
    "vtag, expected_vtag",
    [
        ("v1.11.34", "v1.11.0"),
        ("v1.11.8", "v1.11.0"),
        ("v1.11.0", "v1.11.0"),
    ],
)
def test__get_release_notes_vtag(vtag: str, expected_vtag: str):
    assert _get_release_notes_vtag(vtag) == expected_vtag
