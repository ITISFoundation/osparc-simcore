# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from simcore_service_webserver.login._controller.rest._rest_exceptions import (
    _is_user_affected_by_db_merge,
)


def _create_fake_product(*, group_id: int | None) -> MagicMock:
    product = MagicMock()
    product.group_id = group_id
    return product


@pytest.fixture
def mock_app() -> web.Application:
    return web.Application()


@pytest.fixture
def mock_products(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Creates fake s4l and s4llite products with distinct group_ids."""
    products = {
        "s4l": _create_fake_product(group_id=10),
        "s4llite": _create_fake_product(group_id=20),
    }

    def _get_product(_app: web.Application, product_name: str) -> MagicMock:
        return products[product_name]

    monkeypatch.setattr(
        "simcore_service_webserver.login._controller.rest._rest_exceptions.products_service.get_product",
        _get_product,
    )
    return products


@pytest.fixture
def mock_is_user_in_group(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(return_value=False)
    monkeypatch.setattr(
        "simcore_service_webserver.login._controller.rest._rest_exceptions.groups_service.is_user_in_group",
        mock,
    )
    return mock


async def test_user_in_both_merged_products_is_detected(
    mock_app: web.Application,
    mock_products: dict[str, MagicMock],
    mock_is_user_in_group: AsyncMock,
):
    # User belongs to both s4l (group_id=10) and s4llite (group_id=20)
    mock_is_user_in_group.return_value = True

    result = await _is_user_affected_by_db_merge(mock_app, user_id=42)

    assert result is True


async def test_user_in_only_one_product_is_not_affected(
    mock_app: web.Application,
    mock_products: dict[str, MagicMock],
    mock_is_user_in_group: AsyncMock,
):
    # User only belongs to s4l (group_id=10), not s4llite (group_id=20)
    async def _selective_membership(_app: web.Application, *, user_id: int, group_id: int):
        return group_id == 10  # only in s4l

    mock_is_user_in_group.side_effect = _selective_membership

    result = await _is_user_affected_by_db_merge(mock_app, user_id=42)

    assert result is False


async def test_user_in_no_merged_products_is_not_affected(
    mock_app: web.Application,
    mock_products: dict[str, MagicMock],
    mock_is_user_in_group: AsyncMock,
):
    mock_is_user_in_group.return_value = False

    result = await _is_user_affected_by_db_merge(mock_app, user_id=42)

    assert result is False


async def test_db_merge_check_handles_exceptions_gracefully(
    mock_app: web.Application,
    mock_products: dict[str, MagicMock],
    mock_is_user_in_group: AsyncMock,
):
    # Simulate a DB error — should return False, not raise
    mock_is_user_in_group.side_effect = RuntimeError("DB connection failed")

    result = await _is_user_affected_by_db_merge(mock_app, user_id=42)

    assert result is False


async def test_db_merge_check_handles_missing_product_gracefully(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    # Product not found in app cache
    def _get_product(_app: web.Application, product_name: str) -> MagicMock:
        raise KeyError(product_name)

    monkeypatch.setattr(
        "simcore_service_webserver.login._controller.rest._rest_exceptions.products_service.get_product",
        _get_product,
    )

    result = await _is_user_affected_by_db_merge(mock_app, user_id=42)

    assert result is False


async def test_db_merge_check_skips_product_without_group_id(
    mock_app: web.Application,
    monkeypatch: pytest.MonkeyPatch,
    mock_is_user_in_group: AsyncMock,
):
    # s4l has no group_id, s4llite has one — user is in s4llite but not enough
    products = {
        "s4l": _create_fake_product(group_id=None),
        "s4llite": _create_fake_product(group_id=20),
    }

    def _get_product(_app: web.Application, product_name: str) -> MagicMock:
        return products[product_name]

    monkeypatch.setattr(
        "simcore_service_webserver.login._controller.rest._rest_exceptions.products_service.get_product",
        _get_product,
    )
    mock_is_user_in_group.return_value = True

    result = await _is_user_affected_by_db_merge(mock_app, user_id=42)

    assert result is False
