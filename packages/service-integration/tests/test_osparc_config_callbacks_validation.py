# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Tests that service-integration (ooil) rejects new services with invalid
callbacks_mapping.inactivity.service at publish time.

NOTE: The runtime (DynamicSidecarServiceLabels) intentionally does NOT validate
inactivity to avoid breaking already-deployed services. But at publish time we
must be strict so no new services with bad configs get through.
"""

from typing import Any

import pytest
from models_library.services_resources import DEFAULT_SINGLE_SERVICE_NAME
from pydantic import ValidationError
from service_integration.osparc_config import RuntimeConfig

_COMPOSE_SPEC: dict[str, Any] = {
    "version": "2.3",
    "services": {"rt-web": {"image": "foo"}, "s4l-core": {"image": "bar"}},
}


def _cmd(service: str) -> dict[str, Any]:
    return {"service": service, "command": "ls", "timeout": 1}


def _make_runtime_config(
    callbacks_mapping: dict[str, Any],
    compose_spec: dict[str, Any] | None = None,
    container_http_entrypoint: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if callbacks_mapping:
        data["callbacks-mapping"] = callbacks_mapping
    if compose_spec is not None:
        data["compose-spec"] = compose_spec
    if container_http_entrypoint is not None:
        data["container-http-entrypoint"] = container_http_entrypoint
    return data


@pytest.mark.parametrize(
    "callbacks_mapping, compose_spec, container_http_entrypoint",
    [
        pytest.param(
            {"inactivity": _cmd(DEFAULT_SINGLE_SERVICE_NAME)},
            None,
            None,
            id="inactivity-no-compose-default-service-ok",
        ),
        pytest.param(
            {"inactivity": _cmd("rt-web")},
            _COMPOSE_SPEC,
            "rt-web",
            id="inactivity-with-compose-valid-service-ok",
        ),
        pytest.param(
            {"inactivity": _cmd("s4l-core")},
            _COMPOSE_SPEC,
            "rt-web",
            id="inactivity-with-compose-other-valid-service-ok",
        ),
        pytest.param(
            {"inactivity": _cmd("rt-web"), "metrics": _cmd("s4l-core")},
            _COMPOSE_SPEC,
            "rt-web",
            id="inactivity-and-metrics-both-valid-ok",
        ),
        pytest.param(
            {},
            None,
            None,
            id="empty-callbacks-no-compose-ok",
        ),
    ],
)
def test_runtime_config_inactivity_valid(
    callbacks_mapping: dict[str, Any],
    compose_spec: dict[str, Any] | None,
    container_http_entrypoint: str | None,
):
    data = _make_runtime_config(callbacks_mapping, compose_spec, container_http_entrypoint)
    assert RuntimeConfig.model_validate(data)


@pytest.mark.parametrize(
    "callbacks_mapping, compose_spec, container_http_entrypoint, match_error",
    [
        pytest.param(
            {"inactivity": _cmd("wrong-name")},
            None,
            None,
            "inactivity.service must be",
            id="inactivity-no-compose-wrong-service-rejected",
        ),
        pytest.param(
            {"inactivity": _cmd("not-in-compose")},
            _COMPOSE_SPEC,
            "rt-web",
            "not found in compose-spec services",
            id="inactivity-with-compose-invalid-service-rejected",
        ),
        pytest.param(
            {"inactivity": _cmd("not-in-compose"), "metrics": _cmd("rt-web")},
            _COMPOSE_SPEC,
            "rt-web",
            "not found in compose-spec services",
            id="inactivity-invalid-metrics-valid-still-rejected",
        ),
    ],
)
def test_runtime_config_inactivity_invalid(
    callbacks_mapping: dict[str, Any],
    compose_spec: dict[str, Any] | None,
    container_http_entrypoint: str | None,
    match_error: str,
):
    data = _make_runtime_config(callbacks_mapping, compose_spec, container_http_entrypoint)
    with pytest.raises(ValidationError, match=match_error):
        RuntimeConfig.model_validate(data)
