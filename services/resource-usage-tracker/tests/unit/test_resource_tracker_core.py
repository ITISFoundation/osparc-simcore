# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import re
from typing import Awaitable, Callable
from unittest import mock

import pytest
import requests_mock
from faker import Faker
from fastapi import FastAPI
from simcore_service_resource_usage_tracker.core.settings import ApplicationSettings
from simcore_service_resource_usage_tracker.resource_tracker_core import (
    collect_service_resource_usage,
)


@pytest.fixture
def minimal_configuration(
    mocked_prometheus: requests_mock.Mocker,
    disabled_tracker_background_task: dict[str, mock.Mock],
    initialized_app: FastAPI,
) -> None:
    assert initialized_app
    disabled_tracker_background_task["start_task"].assert_called_once()


@pytest.fixture
def trigger_collect_service_resource_usage(
    initialized_app: FastAPI,
) -> Callable[[], Awaitable[None]]:
    async def _triggerer() -> None:
        return await collect_service_resource_usage(initialized_app)

    return _triggerer


@pytest.fixture
def get_metric_response(faker: Faker):
    def _get_metric(request, context):
        return {
            "data": {
                "result": [
                    {
                        "metric": {
                            "id": "cpu",
                            "container_label_uuid": faker.uuid4(),
                            "container_label_simcore_service_settings": json.dumps(
                                [
                                    {
                                        "name": "Resources",
                                        "type": "Resources",
                                        "resources": faker.pystr(),
                                        "value": {
                                            "Limits": {
                                                "NanoCPUs": faker.pyint(min_value=1000)
                                            }
                                        },
                                    }
                                ]
                            ),
                        },
                        "value": faker.pylist(allowed_types=(int,)),
                    }
                ]
            }
        }

    return _get_metric


@pytest.fixture
def mocked_prometheus(
    mocked_prometheus: requests_mock.Mocker,
    app_settings: ApplicationSettings,
    faker: Faker,
    get_metric_response,
) -> requests_mock.Mocker:
    """overrides with needed calls here"""
    assert app_settings.RESOURCE_USAGE_TRACKER_PROMETHEUS
    pattern = re.compile(
        rf"^{re.escape(app_settings.RESOURCE_USAGE_TRACKER_PROMETHEUS.api_url)}/api/v1/query\?.*$"
    )
    mocked_prometheus.get(pattern, json=get_metric_response)
    return mocked_prometheus


async def test_triggering(
    minimal_configuration: None,
    mocked_prometheus: requests_mock.Mocker,
    trigger_collect_service_resource_usage: Callable[[], Awaitable[None]],
):
    await trigger_collect_service_resource_usage()
