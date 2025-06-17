# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-importimport asyncio
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from models_library.wallets import WalletID
from simcore_service_webserver.notifications import wallet_osparc_credits


@pytest.fixture
def app_with_wallets():
    app = {
        "wallet_subscription_lock": asyncio.Lock(),
        "wallet_subscriptions": {},
    }
    return app


@pytest.fixture
def wallet_id():
    return WalletID(1)


async def test_subscribe_first_and_second(app_with_wallets, wallet_id):
    app = app_with_wallets
    app["wallet_subscriptions"][wallet_id] = 0
    mock_rabbit = AsyncMock()
    with patch(
        "simcore_service_webserver.notifications.wallet_osparc_credits.get_rabbitmq_client",
        return_value=mock_rabbit,
    ):
        await wallet_osparc_credits.subscribe(app, wallet_id)
        mock_rabbit.add_topics.assert_awaited_once()
        # Second subscribe should not call add_topics again
        await wallet_osparc_credits.subscribe(app, wallet_id)
        assert mock_rabbit.add_topics.await_count == 1
        assert app["wallet_subscriptions"][wallet_id] == 2


async def test_unsubscribe_last_and_not_last(app_with_wallets, wallet_id):
    app = app_with_wallets
    app["wallet_subscriptions"][wallet_id] = 2
    mock_rabbit = AsyncMock()
    with patch(
        "simcore_service_webserver.notifications.wallet_osparc_credits.get_rabbitmq_client",
        return_value=mock_rabbit,
    ):
        # Not last unsubscribe
        await wallet_osparc_credits.unsubscribe(app, wallet_id)
        mock_rabbit.remove_topics.assert_not_awaited()
        assert app["wallet_subscriptions"][wallet_id] == 1
        # Last unsubscribe
        await wallet_osparc_credits.unsubscribe(app, wallet_id)
        mock_rabbit.remove_topics.assert_awaited_once()
        assert app["wallet_subscriptions"][wallet_id] == 0


async def test_unsubscribe_when_not_subscribed(app_with_wallets, wallet_id):
    app = app_with_wallets
    # wallet_id not present
    mock_rabbit = AsyncMock()
    with patch(
        "simcore_service_webserver.notifications.wallet_osparc_credits.get_rabbitmq_client",
        return_value=mock_rabbit,
    ):
        await wallet_osparc_credits.unsubscribe(app, wallet_id)
        mock_rabbit.remove_topics.assert_not_awaited()
        assert app["wallet_subscriptions"].get(wallet_id, 0) == 0
