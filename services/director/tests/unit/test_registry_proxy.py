# pylint: disable=W0613, W0621
# pylint: disable=unused-variable

import asyncio
import json
import logging
import time
from unittest import mock

import httpx
import pytest
import respx
from fastapi import FastAPI, status
from pytest_benchmark.plugin import BenchmarkFixture
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.docker_registry import RegistrySettings
from simcore_service_director import registry_proxy
from simcore_service_director.core.settings import ApplicationSettings, get_application_settings

_logger = logging.getLogger(__name__)


async def test_list_no_services_available(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
):
    computational_services = await registry_proxy.list_services(app, registry_proxy.ServiceType.COMPUTATIONAL)
    assert not computational_services  # it's empty
    interactive_services = await registry_proxy.list_services(app, registry_proxy.ServiceType.DYNAMIC)
    assert not interactive_services
    all_services = await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
    assert not all_services


async def test_list_computational_services(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    await push_services(number_of_computational_services=6, number_of_interactive_services=3)

    computational_services = await registry_proxy.list_services(app, registry_proxy.ServiceType.COMPUTATIONAL)
    assert len(computational_services) == 6


async def test_list_interactive_services(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    await push_services(number_of_computational_services=5, number_of_interactive_services=4)
    interactive_services = await registry_proxy.list_services(app, registry_proxy.ServiceType.DYNAMIC)
    assert len(interactive_services) == 4


async def test_list_of_image_tags(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    images = await push_services(number_of_computational_services=5, number_of_interactive_services=3)
    image_number = {}
    for image in images:
        service_description = image["service_description"]
        key = service_description["key"]
        if key not in image_number:
            image_number[key] = 0
        image_number[key] = image_number[key] + 1

    for key, number in image_number.items():
        list_of_image_tags = await registry_proxy.list_image_tags(app, key)
        assert len(list_of_image_tags) == number


async def test_list_interactive_service_dependencies(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    images = await push_services(
        number_of_computational_services=2,
        number_of_interactive_services=2,
        inter_dependent_services=True,
    )
    for image in images:
        service_description = image["service_description"]
        docker_labels = image["docker_labels"]
        if "simcore.service.dependencies" in docker_labels:
            docker_dependencies = json.loads(docker_labels["simcore.service.dependencies"])
            image_dependencies = await registry_proxy.list_interactive_service_dependencies(
                app,
                service_description["key"],
                service_description["version"],
            )
            assert isinstance(image_dependencies, list)
            assert len(image_dependencies) == len(docker_dependencies)
            assert image_dependencies[0]["key"] == docker_dependencies[0]["key"]
            assert image_dependencies[0]["tag"] == docker_dependencies[0]["tag"]


@pytest.fixture(params=["docker_registry", "docker_registry_v2"], ids=["registry_v3", "registry_v2"])
def configure_registry_access_both_versions(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> EnvVarsDict:
    """Parametrized fixture that tests with both registry v3 and v2 - use only for specific tests that need both"""
    registry_url = request.getfixturevalue(request.param)
    return app_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            "REGISTRY_URL": registry_url,
            "REGISTRY_PATH": registry_url,
            "REGISTRY_SSL": False,
            "DIRECTOR_REGISTRY_CACHING": False,
        },
    )


async def test_get_image_labels(
    configure_registry_access_both_versions: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    images = await push_services(
        number_of_computational_services=1,
        number_of_interactive_services=1,
        override_registry_url=configure_registry_access_both_versions["REGISTRY_URL"],
    )
    images_digests = set()
    for image in images:
        service_description = image["service_description"]
        labels, image_manifest_digest = await registry_proxy.get_image_labels(
            app, service_description["key"], service_description["version"]
        )
        assert "io.simcore.key" in labels
        assert "io.simcore.version" in labels
        assert "io.simcore.type" in labels
        assert "io.simcore.name" in labels
        assert "io.simcore.description" in labels
        assert "io.simcore.authors" in labels
        assert "io.simcore.contact" in labels
        assert "io.simcore.inputs" in labels
        assert "io.simcore.outputs" in labels
        if service_description["type"] == "dynamic":
            # dynamic services have this additional flag
            assert "simcore.service.settings" in labels

        assert image_manifest_digest == await registry_proxy.get_image_digest(
            app, service_description["key"], service_description["version"]
        )
        assert image_manifest_digest is not None
        assert image_manifest_digest not in images_digests
        images_digests.add(image_manifest_digest)


def test_get_service_first_name():
    repo = "simcore/services/dynamic/myservice/modeler/my-sub-modeler"
    assert registry_proxy.get_service_first_name(repo) == "myservice"
    repo = "simcore/services/dynamic/myservice/modeler"
    assert registry_proxy.get_service_first_name(repo) == "myservice"
    repo = "simcore/services/dynamic/myservice"
    assert registry_proxy.get_service_first_name(repo) == "myservice"
    repo = "simcore/services/comp/myservice"
    assert registry_proxy.get_service_first_name(repo) == "myservice"
    repo = "simcore/services/comp/myservice/modeler"
    assert registry_proxy.get_service_first_name(repo) == "myservice"
    repo = "simcore/services/comp/myservice/modeler/blahblahblah"
    assert registry_proxy.get_service_first_name(repo) == "myservice"
    repo = "simcore/services/comp"
    assert registry_proxy.get_service_first_name(repo) == "invalid service"

    repo = "services/myservice/modeler/my-sub-modeler"
    assert registry_proxy.get_service_first_name(repo) == "invalid service"


def test_get_service_last_names():
    repo = "simcore/services/dynamic/myservice/modeler/my-sub-modeler"
    assert registry_proxy.get_service_last_names(repo) == "myservice_modeler_my-sub-modeler"
    repo = "simcore/services/dynamic/myservice/modeler"
    assert registry_proxy.get_service_last_names(repo) == "myservice_modeler"
    repo = "simcore/services/dynamic/myservice"
    assert registry_proxy.get_service_last_names(repo) == "myservice"
    repo = "simcore/services/dynamic"
    assert registry_proxy.get_service_last_names(repo) == "invalid service"
    repo = "simcore/services/comp/myservice/modeler"
    assert registry_proxy.get_service_last_names(repo) == "myservice_modeler"
    repo = "services/dynamic/modeler"
    assert registry_proxy.get_service_last_names(repo) == "invalid service"


async def test_get_image_details(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    images = await push_services(number_of_computational_services=1, number_of_interactive_services=1)
    for image in images:
        service_description = image["service_description"]
        details = await registry_proxy.get_image_details(
            app, service_description["key"], service_description["version"]
        )

        assert details.pop("image_digest").startswith("sha")

        assert details == service_description


async def test_list_services(
    configure_registry_access: EnvVarsDict,
    configure_number_concurrency_calls: EnvVarsDict,
    app: FastAPI,
    push_services,
):
    await push_services(number_of_computational_services=21, number_of_interactive_services=21)
    services = await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
    assert len(services) == 42


@pytest.fixture
def configure_registry_caching(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(monkeypatch, {"DIRECTOR_REGISTRY_CACHING": True})


@pytest.fixture
def with_disabled_auto_caching(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch("simcore_service_director.registry_proxy._list_all_services_task", autospec=True)


async def test_registry_caching(
    configure_registry_access: EnvVarsDict,
    configure_registry_caching: EnvVarsDict,
    with_disabled_auto_caching: mock.Mock,
    app_settings: ApplicationSettings,
    app: FastAPI,
    push_services,
):
    images = await push_services(number_of_computational_services=201, number_of_interactive_services=201)
    assert app_settings.DIRECTOR_REGISTRY_CACHING is True

    start_time = time.perf_counter()
    services = await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
    time_to_retrieve_without_cache = time.perf_counter() - start_time
    assert len(services) == len(images)
    start_time = time.perf_counter()
    services = await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
    time_to_retrieve_with_cache = time.perf_counter() - start_time
    assert len(services) == len(images)
    assert time_to_retrieve_with_cache < time_to_retrieve_without_cache
    print("time to retrieve services without cache: ", time_to_retrieve_without_cache)
    print("time to retrieve services with cache: ", time_to_retrieve_with_cache)


@pytest.fixture
def configure_number_concurrency_calls(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            "DIRECTOR_REGISTRY_CLIENT_MAX_CONCURRENT_CALLS": "50",
            "DIRECTOR_REGISTRY_CLIENT_MAX_NUMBER_OF_RETRIEVED_OBJECTS": "50",
        },
    )


def test_list_services_performance(
    skip_if_no_external_envfile: None,
    configure_external_registry_access: EnvVarsDict,
    configure_number_concurrency_calls: EnvVarsDict,
    registry_settings: RegistrySettings,
    app: FastAPI,
    benchmark: BenchmarkFixture,
):
    async def _list_services():
        start_time = time.perf_counter()
        services = await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
        stop_time = time.perf_counter()
        elapsed = stop_time - start_time
        rate = elapsed / len(services or [1])
        _logger.info(
            "Time to list services: %.3fs, %d services in %s, rate: %.3fs/service",
            elapsed,
            len(services),
            registry_settings.resolved_registry_url,
            rate,
        )

    def run_async_test() -> None:
        asyncio.get_event_loop().run_until_complete(_list_services())

    benchmark.pedantic(run_async_test, rounds=5)


async def test_get_image_labels_follows_blob_redirect(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
):
    """When REGISTRY_STORAGE_REDIRECT_DISABLE=false the registry returns HTTP 307
    for blob requests, redirecting to an S3 pre-signed URL.  Verify that the
    director follows the redirect and correctly parses the JSON config blob."""

    image = "simcore/services/comp/test-redirect"
    tag = "1.0.0"
    config_digest = "sha256:abc123def456"
    manifest_digest = "sha256:manifest_digest_789"
    s3_presigned_url = (
        "https://s3.amazonaws.com/registry-bucket/blobs/abc123?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=fake"
    )

    manifest_response = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
        "config": {
            "mediaType": "application/vnd.docker.container.image.v1+json",
            "digest": config_digest,
            "size": 1234,
        },
        "layers": [],
    }

    expected_labels = {
        "io.simcore.key": '{"key": "simcore/services/comp/test-redirect"}',
        "io.simcore.version": '{"version": "1.0.0"}',
        "io.simcore.type": '{"type": "computational"}',
        "io.simcore.name": '{"name": "test-redirect"}',
        "io.simcore.description": '{"description": "A test service"}',
        "io.simcore.authors": '{"authors": [{"name": "test"}]}',
        "io.simcore.contact": '{"contact": "test@test.com"}',
        "io.simcore.inputs": '{"inputs": {}}',
        "io.simcore.outputs": '{"outputs": {}}',
    }
    config_blob_response = {"config": {"Labels": expected_labels}}

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get(url__contains=f"{image}/manifests/{tag}").respond(
            status.HTTP_200_OK,
            json=manifest_response,
            headers={
                "Docker-Content-Digest": manifest_digest,
                "Content-Type": "application/vnd.docker.distribution.manifest.v2+json",
            },
        )
        respx_mock.get(url__contains=f"{image}/blobs/{config_digest}").respond(
            status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": s3_presigned_url},
        )
        respx_mock.get(url__contains="s3.amazonaws.com").respond(
            status.HTTP_200_OK,
            json=config_blob_response,
        )

        labels, digest = await registry_proxy.get_image_labels(app, image, tag)

        assert labels == expected_labels
        assert digest == manifest_digest

        # Verify no auth leaked to S3
        s3_calls = [c for c in respx_mock.calls if "s3.amazonaws.com" in str(c.request.url)]
        assert len(s3_calls) == 1
        assert "authorization" not in {k.lower() for k in s3_calls[0].request.headers}


@pytest.fixture
def configure_authed_registry_access(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    docker_registry: str,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            "REGISTRY_URL": docker_registry,
            "REGISTRY_PATH": docker_registry,
            "REGISTRY_AUTH": "true",
            "REGISTRY_USER": "testuser",
            "REGISTRY_PW": "testpassword",
            "REGISTRY_SSL": "false",
            "DIRECTOR_REGISTRY_CACHING": "false",
        },
    )


async def test_get_image_labels_follows_blob_redirect_with_basic_auth(
    configure_authed_registry_access: EnvVarsDict,
    app: FastAPI,
):
    """Production-like scenario: REGISTRY_AUTH=true, basic auth accepted,
    blob requests return 307 redirect to S3 pre-signed URL."""

    image = "simcore/services/dynamic/test-auth-redirect"
    tag = "2.0.0"
    config_digest = "sha256:auth_cfg_digest_001"
    manifest_digest = "sha256:auth_manifest_digest_002"
    s3_presigned_url = (
        "https://my-bucket.s3.us-east-1.amazonaws.com/docker/blobs/sha256/auth_cfg_digest_001"
        "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires=1200&X-Amz-Signature=abcdef"
    )

    manifest_response = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
        "config": {
            "mediaType": "application/vnd.docker.container.image.v1+json",
            "digest": config_digest,
            "size": 5678,
        },
        "layers": [
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "digest": "sha256:layer1",
                "size": 100,
            }
        ],
    }

    expected_labels = {
        "io.simcore.key": '{"key": "simcore/services/dynamic/test-auth-redirect"}',
        "io.simcore.version": '{"version": "2.0.0"}',
        "io.simcore.type": '{"type": "dynamic"}',
        "io.simcore.name": '{"name": "test-auth-redirect"}',
        "io.simcore.description": '{"description": "Auth redirect test"}',
        "io.simcore.authors": '{"authors": [{"name": "test"}]}',
        "io.simcore.contact": '{"contact": "test@test.com"}',
        "io.simcore.inputs": '{"inputs": {}}',
        "io.simcore.outputs": '{"outputs": {}}',
        "simcore.service.settings": "[]",
    }
    config_blob_response = {"config": {"Labels": expected_labels}}

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get(url__contains=f"{image}/manifests/{tag}").respond(
            status.HTTP_200_OK,
            json=manifest_response,
            headers={
                "Docker-Content-Digest": manifest_digest,
                "Content-Type": "application/vnd.docker.distribution.manifest.v2+json",
            },
        )
        respx_mock.get(url__contains=f"{image}/blobs/{config_digest}").respond(
            status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": s3_presigned_url},
        )
        respx_mock.get(url__contains="s3.us-east-1.amazonaws.com").respond(
            status.HTTP_200_OK,
            json=config_blob_response,
        )

        labels, digest = await registry_proxy.get_image_labels(app, image, tag)

        assert labels == expected_labels
        assert digest == manifest_digest

        # Verify requests sequence: manifest, blob (307), S3 follow
        assert len(respx_mock.calls) == 3
        assert "manifests" in str(respx_mock.calls[0].request.url)
        assert respx_mock.calls[0].request.headers.get("authorization")  # manifest has auth
        assert "blobs" in str(respx_mock.calls[1].request.url)
        assert respx_mock.calls[1].request.headers.get("authorization")  # blob has auth
        assert "s3.us-east-1.amazonaws.com" in str(respx_mock.calls[2].request.url)
        assert not respx_mock.calls[2].request.headers.get("authorization")  # S3 must NOT have auth


async def test_get_image_labels_no_redirect_still_works(
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
):
    """Regression test: when REGISTRY_STORAGE_REDIRECT_DISABLE=true (default),
    blob requests return 200 directly.  Verify follow_redirects=True does not
    break the normal non-redirect path."""

    image = "simcore/services/comp/test-no-redirect"
    tag = "1.0.0"
    config_digest = "sha256:noredir_cfg_001"
    manifest_digest = "sha256:noredir_manifest_001"

    manifest_response = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
        "config": {
            "mediaType": "application/vnd.docker.container.image.v1+json",
            "digest": config_digest,
            "size": 1000,
        },
        "layers": [],
    }

    expected_labels = {
        "io.simcore.key": '{"key": "simcore/services/comp/test-no-redirect"}',
        "io.simcore.version": '{"version": "1.0.0"}',
        "io.simcore.type": '{"type": "computational"}',
        "io.simcore.name": '{"name": "test-no-redirect"}',
        "io.simcore.description": '{"description": "No redirect test"}',
        "io.simcore.authors": '{"authors": [{"name": "test"}]}',
        "io.simcore.contact": '{"contact": "test@test.com"}',
        "io.simcore.inputs": '{"inputs": {}}',
        "io.simcore.outputs": '{"outputs": {}}',
    }
    config_blob_response = {"config": {"Labels": expected_labels}}

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get(url__contains=f"{image}/manifests/{tag}").respond(
            status.HTTP_200_OK,
            json=manifest_response,
            headers={
                "Docker-Content-Digest": manifest_digest,
                "Content-Type": "application/vnd.docker.distribution.manifest.v2+json",
            },
        )
        respx_mock.get(url__contains=f"{image}/blobs/{config_digest}").respond(
            status.HTTP_200_OK,
            json=config_blob_response,
        )

        labels, digest = await registry_proxy.get_image_labels(app, image, tag)

        assert labels == expected_labels
        assert digest == manifest_digest


async def test_get_image_labels_follows_blob_redirect_with_bearer_auth(
    configure_authed_registry_access: EnvVarsDict,
    app: FastAPI,
):
    """Bearer token auth flow: initial request returns 401 with WWW-Authenticate
    Bearer challenge, director fetches a token, then retries.  Blob requests
    return 307 redirect to S3 pre-signed URL."""

    image = "simcore/services/dynamic/test-bearer-redirect"
    tag = "3.0.0"
    config_digest = "sha256:bearer_cfg_001"
    manifest_digest = "sha256:bearer_manifest_001"
    s3_presigned_url = (
        "https://my-bucket.s3.us-east-1.amazonaws.com"
        "/docker/blobs/sha256/bearer_cfg_001"
        "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=bearertest"
    )
    fake_token = "fake-bearer-token-12345"  # noqa: S105

    manifest_response = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
        "config": {
            "mediaType": "application/vnd.docker.container.image.v1+json",
            "digest": config_digest,
            "size": 2000,
        },
        "layers": [],
    }

    expected_labels = {
        "io.simcore.key": ('{"key": "simcore/services/dynamic/test-bearer-redirect"}'),
        "io.simcore.version": '{"version": "3.0.0"}',
        "io.simcore.type": '{"type": "dynamic"}',
        "io.simcore.name": '{"name": "test-bearer-redirect"}',
        "io.simcore.description": '{"description": "Bearer redirect test"}',
        "io.simcore.authors": '{"authors": [{"name": "test"}]}',
        "io.simcore.contact": '{"contact": "test@test.com"}',
        "io.simcore.inputs": '{"inputs": {}}',
        "io.simcore.outputs": '{"outputs": {}}',
        "simcore.service.settings": "[]",
    }
    config_blob_response = {"config": {"Labels": expected_labels}}

    app_settings = get_application_settings(app)
    realm_url = f"http://{app_settings.DIRECTOR_REGISTRY.REGISTRY_URL}/v2/token"

    def _bearer_manifest_handler(request: httpx.Request) -> httpx.Response:
        if f"Bearer {fake_token}" not in request.headers.get("authorization", ""):
            return httpx.Response(
                status.HTTP_401_UNAUTHORIZED,
                headers={
                    "WWW-Authenticate": (
                        f'Bearer realm="{realm_url}",service="registry.example.com",scope="repository:{image}:pull"'
                    )
                },
            )
        return httpx.Response(
            status.HTTP_200_OK,
            json=manifest_response,
            headers={
                "Docker-Content-Digest": manifest_digest,
                "Content-Type": "application/vnd.docker.distribution.manifest.v2+json",
            },
        )

    def _bearer_blob_handler(request: httpx.Request) -> httpx.Response:
        if f"Bearer {fake_token}" not in request.headers.get("authorization", ""):
            return httpx.Response(
                status.HTTP_401_UNAUTHORIZED,
                headers={
                    "WWW-Authenticate": (
                        f'Bearer realm="{realm_url}",service="registry.example.com",scope="repository:{image}:pull"'
                    )
                },
            )
        return httpx.Response(
            status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": s3_presigned_url},
        )

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get(url__contains="/v2/token").respond(status.HTTP_200_OK, json={"token": fake_token})
        respx_mock.get(url__contains=f"{image}/manifests/{tag}").mock(side_effect=_bearer_manifest_handler)
        respx_mock.get(url__contains=f"{image}/blobs/{config_digest}").mock(side_effect=_bearer_blob_handler)
        respx_mock.get(url__contains="s3.us-east-1.amazonaws.com").respond(
            status.HTTP_200_OK, json=config_blob_response
        )

        labels, digest = await registry_proxy.get_image_labels(app, image, tag)

        assert labels == expected_labels
        assert digest == manifest_digest

        # Verify Bearer flow: at least one 401→token→retry cycle happened
        token_calls = [c for c in respx_mock.calls if "/v2/token" in str(c.request.url)]
        assert len(token_calls) >= 1, "Expected token exchange request"

        s3_calls = [c for c in respx_mock.calls if "s3.us-east-1.amazonaws.com" in str(c.request.url)]
        assert len(s3_calls) == 1, "Expected exactly one S3 redirect follow"
        assert not s3_calls[0].request.headers.get("authorization"), "Authorization header leaked to S3"
