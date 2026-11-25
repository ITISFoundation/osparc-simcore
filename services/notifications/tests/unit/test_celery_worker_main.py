# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from celery import Celery
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict


def test_worker_app_disables_extended_result_metadata(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    """Extended result metadata stores task arguments verbatim in the result
    backend; SMS task arguments carry verification codes and phone numbers, so
    the notifications workers must boot with the flag off.
    """
    monkeypatch.setenv("NOTIFICATIONS_BOOT_SERVER_MODE", "AS_CELERY_WORKER")
    monkeypatch.setenv("NOTIFICATIONS_CELERY_QUEUES", "notifications-email")

    created_apps: list[Celery] = []

    def _fake_create_worker_app(*args, **kwargs) -> Celery:
        app = Celery("notifications-test")
        # celery-library's shared base config enables the extended metadata
        app.conf.result_extended = True
        created_apps.append(app)
        return app

    monkeypatch.setattr(
        "celery_library.worker.app.create_worker_app", _fake_create_worker_app
    )

    from simcore_service_notifications.modules.celery import worker_main

    assert created_apps
    assert all(app.conf.result_extended is False for app in created_apps)
    assert worker_main.app.conf.result_extended is False
