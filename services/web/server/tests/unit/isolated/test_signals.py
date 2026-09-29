# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Guards for the centralized observer event labels in ``signals``.

These labels are the keys of the observer registry (see
``servicelib.aiohttp.observer``): an emitter and its observers only meet if they
use the *same* string, and the keys also surface in replica logs/reports. The
tests below lock that contract so a rename or drift is caught here instead of
silently breaking wallet bootstrap, socket logout or project/wallet
subscription at runtime.

They are intentionally DB/socket-free (isolated): they exercise the registration
and emit seams only, not the (heavier) observers' side effects.
"""

import ast
import inspect
from collections.abc import Callable
from typing import Any

import pytest
from aiohttp import web
from pytest_mock import MockerFixture
from servicelib.aiohttp.observer import (
    emit,
    register_observer,
    registered_observers_report,
    setup_observer_registry,
)
from simcore_service_webserver import signals
from simcore_service_webserver.projects._controller.projects_slot import (
    setup_project_observer_events,
)
from simcore_service_webserver.resource_usage._observer import (
    setup_resource_usage_observer_events,
)
from simcore_service_webserver.signals import (
    SIGNAL_ON_USER_CONFIRMATION,
    SIGNAL_USER_CONNECTED,
    SIGNAL_USER_DISCONNECTED,
    SIGNAL_USER_LOGOUT,
)
from simcore_service_webserver.socketio._observer import (
    setup_socketio_observer_events,
)
from simcore_service_webserver.wallets._events import setup_wallets_events

# every label must keep this exact on-the-wire value: it is the registry key
# shared by emitters/observers and appears in logs (registered_observers_report)
_EXPECTED_WIRE_VALUES: dict[str, str] = {
    signals.SIGNAL_ON_USER_CONFIRMATION: "SIGNAL_ON_USER_CONFIRMATION",
    signals.SIGNAL_USER_CONNECTED: "SIGNAL_USER_CONNECTED",
    signals.SIGNAL_USER_DISCONNECTED: "SIGNAL_USER_DISCONNECTED",
    signals.SIGNAL_USER_LOGOUT: "SIGNAL_USER_LOGOUT",
}

# (setup function, label it must register an observer under)
_OBSERVER_SETUPS: list[tuple[Callable[[web.Application], Any], str]] = [
    (setup_wallets_events, SIGNAL_ON_USER_CONFIRMATION),
    (setup_socketio_observer_events, SIGNAL_USER_LOGOUT),
    (setup_project_observer_events, SIGNAL_USER_CONNECTED),
    (setup_project_observer_events, SIGNAL_USER_DISCONNECTED),
    (setup_resource_usage_observer_events, SIGNAL_USER_CONNECTED),
    (setup_resource_usage_observer_events, SIGNAL_USER_DISCONNECTED),
]


@pytest.fixture
def app() -> web.Application:
    _app = web.Application()
    setup_observer_registry(_app)
    return _app


@pytest.mark.parametrize("constant", sorted(_EXPECTED_WIRE_VALUES))
def test_signal_constants_keep_their_wire_value(constant: str):
    assert _EXPECTED_WIRE_VALUES[constant] == constant


def test_signals_module_is_a_pure_leaf():
    """signals must not import the service graph, so it cannot create cycles"""
    tree = ast.parse(inspect.getsource(signals))

    forbidden_roots = {"simcore_service_webserver", "servicelib", "models_library", "common_library"}
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported_roots.add(node.module.split(".")[0])

    assert not imported_roots & forbidden_roots, f"signals must not import {forbidden_roots}, imports {imported_roots}"


@pytest.mark.parametrize(
    "setup_func,expected_event",
    _OBSERVER_SETUPS,
    ids=[f"{f.__name__}->{e}" for f, e in _OBSERVER_SETUPS],
)
def test_observer_setup_registers_under_shared_signal(
    setup_func: Callable[[web.Application], Any],
    expected_event: str,
):
    app = web.Application()
    setup_func(app)

    # registered_observers_report renders " {event}->{n} handles" per event
    report = registered_observers_report(app)
    assert f"{expected_event}->" in report, f"{setup_func.__name__} did not register a handler for {expected_event}"


async def test_notify_user_logout_emits_under_shared_signal(app: web.Application, mocker: MockerFixture):
    # importing lazily keeps the module's heavy import chain out of the other tests
    from simcore_service_webserver.login._login_service import notify_user_logout  # noqa: PLC0415

    probe = mocker.AsyncMock(return_value=None)
    register_observer(app, probe, SIGNAL_USER_LOGOUT)

    await notify_user_logout(app, user_id=42, client_session_id="sess-1")

    probe.assert_awaited_once()
    # positional payload contract: (user_id, client_session_id, app)
    args = probe.await_args.args
    assert args[0] == 42
    assert args[1] == "sess-1"
    assert args[2] is app


async def test_notify_user_confirmation_emits_under_shared_signal(app: web.Application, mocker: MockerFixture):
    from simcore_service_webserver.login._login_service import notify_user_confirmation  # noqa: PLC0415

    probe = mocker.AsyncMock(return_value=None)
    register_observer(app, probe, SIGNAL_ON_USER_CONFIRMATION)

    await notify_user_confirmation(app, user_id=7, product_name="osparc", extra_credits_in_usd=10)

    probe.assert_awaited_once()
    # keyword payload contract
    assert probe.await_args.kwargs == {
        "user_id": 7,
        "product_name": "osparc",
        "extra_credits_in_usd": 10,
    }


async def test_unrelated_signal_does_not_cross_wire(app: web.Application, mocker: MockerFixture):
    """a handler bound to one signal must not be triggered by another"""
    on_connected = mocker.AsyncMock(return_value=None)
    register_observer(app, on_connected, SIGNAL_USER_CONNECTED)

    await emit(app, SIGNAL_USER_DISCONNECTED, 1, "sess", app, "osparc")
    on_connected.assert_not_awaited()

    await emit(app, SIGNAL_USER_CONNECTED, 1, app, "osparc", "sess")
    on_connected.assert_awaited_once()
