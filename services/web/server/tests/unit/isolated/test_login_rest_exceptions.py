# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from simcore_service_webserver.constants import RQ_PRODUCT_KEY
from simcore_service_webserver.groups import api as groups_service
from simcore_service_webserver.login._controller.rest._rest_exceptions import (
    _handle_legacy_error_response,
    _try_show_login_tip,
)
from simcore_service_webserver.login.constants import (
    MSG_WRONG_PASSWORD,
    MSG_WRONG_PASSWORD_MERGED_ACCOUNTS,
)
from simcore_service_webserver.login.errors import WrongPasswordError
from simcore_service_webserver.products import products_service
from simcore_service_webserver.products.errors import ProductNotFoundError


def _create_fake_product(
    *,
    name: str,
    display_name: str = "",
    group_id: int | None,
    tip_products: list[str] | None = None,
) -> MagicMock:
    product = MagicMock()
    product.name = name
    product.display_name = display_name or name
    product.group_id = group_id
    product.vendor = {"marketing_fallback_products_on_wrong_password": tip_products} if tip_products else {}
    return product


@pytest.fixture
def mock_app() -> web.Application:
    return web.Application()


@pytest.fixture
def mock_is_user_in_group(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(return_value=False)
    monkeypatch.setattr(
        f"{groups_service.__name__}.is_user_in_group",
        mock,
    )
    return mock


@pytest.fixture
def patch_products(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[MagicMock]], None]:
    def _patch(all_products: list[MagicMock]) -> None:
        products_by_name = {p.name: p for p in all_products}

        def _get_product(_app: web.Application, product_name: str) -> MagicMock:
            if product_name not in products_by_name:
                raise ProductNotFoundError(product_name=product_name)
            return products_by_name[product_name]

        monkeypatch.setattr(
            f"{products_service.__name__}.get_product",
            _get_product,
        )

    return _patch


@pytest.fixture
def s4l_product() -> MagicMock:
    return _create_fake_product(name="s4l", display_name="Sim4Life", group_id=10)


@pytest.fixture
def s4llite_product() -> MagicMock:
    return _create_fake_product(name="s4llite", group_id=20, tip_products=["s4l"])


@pytest.mark.acceptance_test("For https://github.com/ITISFoundation/private-issues/issues/535")
async def test_tip_returns_preferred_product_display_name(
    mock_app: web.Application,
    patch_products: Callable,
    mock_is_user_in_group: AsyncMock,
    s4l_product: MagicMock,
):
    # s4llite configured to suggest s4l; user belongs to s4l
    s4llite = _create_fake_product(name="s4llite", group_id=20, tip_products=["s4l", "osparc"])
    osparc = _create_fake_product(name="osparc", display_name="o²S²PARC", group_id=30)
    patch_products([s4llite, s4l_product, osparc])
    mock_is_user_in_group.return_value = True

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result == "Sim4Life"


async def test_tip_not_shown_when_no_tip_configured(
    mock_app: web.Application,
    patch_products: Callable,
    mock_is_user_in_group: AsyncMock,
    s4llite_product: MagicMock,
):
    # s4l has no tip configured
    s4l = _create_fake_product(name="s4l", group_id=10)
    patch_products([s4l, s4llite_product])
    mock_is_user_in_group.return_value = True

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4l")

    assert result is None


async def test_tip_not_shown_when_user_not_in_listed_products(
    mock_app: web.Application,
    patch_products: Callable,
    mock_is_user_in_group: AsyncMock,
    s4llite_product: MagicMock,
    s4l_product: MagicMock,
):
    # s4llite configured to check s4l, but user is NOT in s4l
    patch_products([s4llite_product, s4l_product])
    # mock_is_user_in_group defaults to return_value=False

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result is None


async def test_tip_handles_db_error_gracefully(
    mock_app: web.Application,
    patch_products: Callable,
    mock_is_user_in_group: AsyncMock,
    s4llite_product: MagicMock,
    s4l_product: MagicMock,
):
    patch_products([s4llite_product, s4l_product])
    mock_is_user_in_group.side_effect = RuntimeError("DB connection failed")

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result is None


async def test_tip_handles_missing_current_product_gracefully(
    mock_app: web.Application,
    patch_products: Callable,
    mock_is_user_in_group: AsyncMock,
):
    patch_products([])  # no products configured

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="unknown")

    assert result is None


async def test_tip_skips_listed_product_without_group_id(
    mock_app: web.Application,
    patch_products: Callable,
    mock_is_user_in_group: AsyncMock,
    s4llite_product: MagicMock,
):
    # s4llite configured to check s4l, but s4l has no group_id
    s4l_no_group = _create_fake_product(name="s4l", display_name="Sim4Life", group_id=None)
    patch_products([s4llite_product, s4l_no_group])
    mock_is_user_in_group.return_value = True

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result is None


async def test_tip_skips_unknown_listed_product(
    mock_app: web.Application,
    patch_products: Callable,
    mock_is_user_in_group: AsyncMock,
    s4l_product: MagicMock,
):
    # s4llite lists "nonexistent" and "s4l"; nonexistent is skipped, user is in s4l
    s4llite = _create_fake_product(name="s4llite", group_id=20, tip_products=["s4l", "nonexistent"])
    patch_products([s4llite, s4l_product])
    mock_is_user_in_group.return_value = True

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result == "Sim4Life"


async def test_tip_returns_matching_product_not_first(
    mock_app: web.Application,
    patch_products: Callable,
    mock_is_user_in_group: AsyncMock,
):
    """User belongs only to the second listed product; its display name is returned."""
    s4l = _create_fake_product(name="s4l", display_name="Sim4Life", group_id=10)
    osparc = _create_fake_product(name="osparc", display_name="o²S²PARC", group_id=30)
    s4llite = _create_fake_product(name="s4llite", group_id=20, tip_products=["s4l", "osparc"])
    patch_products([s4llite, s4l, osparc])

    async def _is_in_group(_app, *, user_id, group_id):
        # user is only in osparc (group_id=30), not s4l (group_id=10)
        return group_id == 30

    mock_is_user_in_group.side_effect = _is_in_group

    result = await _try_show_login_tip(mock_app, user_id=42, product_name="s4llite")

    assert result == "o²S²PARC"


# ---------------------------------------------------------------------------
# Tests for _handle_legacy_error_response
# ---------------------------------------------------------------------------


def _make_request_with_product(app: web.Application, product_name: str) -> web.Request:
    request = make_mocked_request("POST", "/v0/auth/login", app=app)
    request[RQ_PRODUCT_KEY] = product_name
    return request


def _parse_enveloped_message(response: web.HTTPError) -> str:
    assert response.text is not None
    body = json.loads(response.text)
    return body["error"]["message"]


@pytest.mark.acceptance_test("For https://github.com/ITISFoundation/private-issues/issues/535")
async def test_handler_returns_merged_accounts_message_when_tip_applies(
    mock_app: web.Application,
    patch_products: Callable,
    mock_is_user_in_group: AsyncMock,
    s4llite_product: MagicMock,
    s4l_product: MagicMock,
):
    patch_products([s4llite_product, s4l_product])
    mock_is_user_in_group.return_value = True
    request = _make_request_with_product(mock_app, "s4llite")

    response = await _handle_legacy_error_response(request, WrongPasswordError(user_id=42))

    assert response.status == 401
    msg = _parse_enveloped_message(response)
    expected = MSG_WRONG_PASSWORD_MERGED_ACCOUNTS.format(suggested_product="Sim4Life")
    assert msg == expected


async def test_handler_returns_default_message_when_no_tip(
    mock_app: web.Application,
    patch_products: Callable,
    mock_is_user_in_group: AsyncMock,
):
    # product with no tip configured
    s4l = _create_fake_product(name="s4l", group_id=10)
    patch_products([s4l])
    request = _make_request_with_product(mock_app, "s4l")

    response = await _handle_legacy_error_response(request, WrongPasswordError(user_id=42))

    assert response.status == 401
    msg = _parse_enveloped_message(response)
    assert msg == MSG_WRONG_PASSWORD


async def test_handler_returns_default_message_when_user_not_in_tip_products(
    mock_app: web.Application,
    patch_products: Callable,
    mock_is_user_in_group: AsyncMock,
    s4llite_product: MagicMock,
    s4l_product: MagicMock,
):
    patch_products([s4llite_product, s4l_product])
    # user is NOT in s4l group
    mock_is_user_in_group.return_value = False
    request = _make_request_with_product(mock_app, "s4llite")

    response = await _handle_legacy_error_response(request, WrongPasswordError(user_id=42))

    assert response.status == 401
    msg = _parse_enveloped_message(response)
    assert msg == MSG_WRONG_PASSWORD
