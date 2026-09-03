# pylint: disable=redefined-outer-name

import pytest
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    SIDECAR_HELPERS_RESOURCE_KEY,
    ImageResources,
    ResourcesDict,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pydantic import ByteSize, TypeAdapter
from servicelib.docker_utils import estimate_dynamic_sidecar_resources_from_ec2_instance
from simcore_service_director_v2.core.dynamic_services_settings import (
    DynamicServicesSettings,
)
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs.resources import (
    NotEnoughInstanceResourcesError,
    compute_helper_containers_resources,
    get_max_rclone_container_memory_limit,
    get_max_user_service_container_memory,
    scale_service_resources_to_instance_type,
)


def _image_resources(ram: str) -> ImageResources:
    return ImageResources.model_validate(
        {
            "image": "simcore/services/dynamic/jupyter-math:1.0.0",
            "resources": TypeAdapter(ResourcesDict).validate_python(
                {"RAM": {"limit": TypeAdapter(ByteSize).validate_python(ram), "reservation": 0}}
            ),
        }
    )


@pytest.fixture
def dynamic_services_settings(monkeypatch: pytest.MonkeyPatch) -> DynamicServicesSettings:
    # minimal env required to build the nested settings; no app/DB/docker needed
    for key, value in {
        "DYNAMIC_SIDECAR_IMAGE": "local/dynamic-sidecar:production",
        "DYNAMIC_SIDECAR_PROMETHEUS_SERVICE_LABELS": "{}",
        "DYNAMIC_SIDECAR_SC_BOOT_MODE": "production",
        "R_CLONE_PROVIDER": "MINIO",
        "S3_ACCESS_KEY": "access-key",
        "S3_BUCKET_NAME": "bucket",
        "S3_ENDPOINT": "http://localhost:9000",
        "S3_REGION": "us-east-1",
        "S3_SECRET_KEY": "secret-key",
        "SIMCORE_SERVICES_NETWORK_NAME": "simcore_interactive",
        "SWARM_STACK_NAME": "simcore",
        "TRAEFIK_SIMCORE_ZONE": "internal_simcore_stack",
        "WEBSERVER_HOST": "webserver",
    }.items():
        monkeypatch.setenv(key, value)
    return DynamicServicesSettings.create_from_envs()


@pytest.mark.parametrize(
    "service_resources, expected",
    [
        pytest.param({}, "0", id="no_containers"),
        pytest.param({"container": _image_resources("2GiB")}, "2GiB", id="single_container"),
        pytest.param(
            {"a": _image_resources("1GiB"), "b": _image_resources("4GiB")},
            "4GiB",
            id="largest_of_many",
        ),
        pytest.param(
            {"a": _image_resources("1GiB"), SIDECAR_HELPERS_RESOURCE_KEY: _image_resources("8GiB")},
            "1GiB",
            id="ignores_synthetic_helpers_entry",
        ),
    ],
)
def test_get_max_user_service_container_memory(service_resources: ServiceResourcesDict, expected: str):
    assert get_max_user_service_container_memory(service_resources) == TypeAdapter(ByteSize).validate_python(expected)


@pytest.mark.parametrize(
    "max_user_service_container_memory, expectation",
    [
        pytest.param("1KiB", "clamped_to_min", id="below_min_is_clamped_up"),
        pytest.param("1PiB", "clamped_to_max", id="above_max_is_clamped_down"),
    ],
)
def test_get_max_rclone_container_memory_limit_is_clamped(
    dynamic_services_settings: DynamicServicesSettings,
    max_user_service_container_memory: str,
    expectation: str,
):
    mount_settings = (
        dynamic_services_settings.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_R_CLONE_SETTINGS.R_CLONE_SIMCORE_SDK_MOUNT_SETTINGS
    )
    result = get_max_rclone_container_memory_limit(
        mount_settings, TypeAdapter(ByteSize).validate_python(max_user_service_container_memory)
    )
    if expectation == "clamped_to_min":
        assert result == mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_MEMORY_LIMIT_MIN
    else:
        assert result == mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_MEMORY_LIMIT_MAX


def test_compute_helper_containers_resources_without_helpers_is_zero(
    dynamic_services_settings: DynamicServicesSettings,
):
    cpu, ram = compute_helper_containers_resources(
        dynamic_services_settings=dynamic_services_settings,
        egress_proxy_count=0,
        with_tracing=False,
        with_rclone=False,
        max_user_service_container_memory=TypeAdapter(ByteSize).validate_python("2GiB"),
    )
    assert cpu == 0
    assert ram == 0


@pytest.mark.parametrize("egress_proxy_count", [1, 3])
def test_compute_helper_containers_resources_scales_with_egress_proxies(
    dynamic_services_settings: DynamicServicesSettings, egress_proxy_count: int
):
    egress_settings = dynamic_services_settings.DYNAMIC_SIDECAR_EGRESS_PROXY_SETTINGS

    cpu, ram = compute_helper_containers_resources(
        dynamic_services_settings=dynamic_services_settings,
        egress_proxy_count=egress_proxy_count,
        with_tracing=False,
        with_rclone=False,
        max_user_service_container_memory=TypeAdapter(ByteSize).validate_python("2GiB"),
    )
    assert cpu == egress_proxy_count * egress_settings.DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT.cores
    assert ram == egress_proxy_count * int(egress_settings.DYNAMIC_SIDECAR_ENVOY_MEMORY_LIMIT)


def test_compute_helper_containers_resources_counts_two_tracing_containers(
    dynamic_services_settings: DynamicServicesSettings,
):
    tracing_settings = dynamic_services_settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING_CONFIG

    cpu, ram = compute_helper_containers_resources(
        dynamic_services_settings=dynamic_services_settings,
        egress_proxy_count=0,
        with_tracing=True,
        with_rclone=False,
        max_user_service_container_memory=TypeAdapter(ByteSize).validate_python("2GiB"),
    )
    # otel collector + otel forwarder
    assert cpu == 2 * tracing_settings.USER_SERVICES_TRACING_COLLECTOR_CPU_LIMIT.cores
    assert ram == 2 * int(tracing_settings.USER_SERVICES_TRACING_COLLECTOR_MEMORY_LIMIT)


def test_compute_helper_containers_resources_accumulates_all_helpers(
    dynamic_services_settings: DynamicServicesSettings,
):
    max_user_service_container_memory = TypeAdapter(ByteSize).validate_python("2GiB")
    kwargs = {
        "dynamic_services_settings": dynamic_services_settings,
        "max_user_service_container_memory": max_user_service_container_memory,
    }

    egress_only = compute_helper_containers_resources(
        egress_proxy_count=1, with_tracing=False, with_rclone=False, **kwargs
    )
    tracing_only = compute_helper_containers_resources(
        egress_proxy_count=0, with_tracing=True, with_rclone=False, **kwargs
    )
    rclone_only = compute_helper_containers_resources(
        egress_proxy_count=0, with_tracing=False, with_rclone=True, **kwargs
    )
    all_helpers = compute_helper_containers_resources(
        egress_proxy_count=1, with_tracing=True, with_rclone=True, **kwargs
    )

    assert all_helpers[0] == pytest.approx(egress_only[0] + tracing_only[0] + rclone_only[0])
    assert all_helpers[1] == egress_only[1] + tracing_only[1] + rclone_only[1]


def _single_service_resources(cpu: float, ram: str) -> ServiceResourcesDict:
    return ServiceResourcesDictHelpers.create_from_single_service(
        image="simcore/services/dynamic/jupyter-math:1.0.0",
        resources=TypeAdapter(ResourcesDict).validate_python(
            {
                "CPU": {"limit": cpu, "reservation": cpu},
                "RAM": {"limit": TypeAdapter(ByteSize).validate_python(ram), "reservation": 0},
            }
        ),
    )


def test_scale_service_resources_leaves_room_for_sidecar_and_helpers(
    dynamic_services_settings: DynamicServicesSettings,
):
    instance_cpus, instance_ram = 16, TypeAdapter(ByteSize).validate_python("128GiB")

    scaled = scale_service_resources_to_instance_type(
        _single_service_resources(0.1, "2GiB"),
        dynamic_services_settings=dynamic_services_settings,
        egress_proxy_count=0,
        with_tracing=False,
        with_rclone=False,
        instance_cpus=instance_cpus,
        instance_ram=instance_ram,
    )

    resources = scaled[DEFAULT_SINGLE_SERVICE_NAME].resources
    sidecar_own = dynamic_services_settings.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_OWN_CPU_LIMIT.cores
    available_cpus, _ = estimate_dynamic_sidecar_resources_from_ec2_instance(instance_cpus, instance_ram)
    # the sidecar's own share is carved out of what the user service gets
    assert float(resources["CPU"].limit) == pytest.approx(available_cpus - sidecar_own)
    assert int(resources["RAM"].limit) < int(instance_ram)


def test_scale_service_resources_raises_when_instance_too_small(
    dynamic_services_settings: DynamicServicesSettings,
):
    with pytest.raises(NotEnoughInstanceResourcesError):
        scale_service_resources_to_instance_type(
            _single_service_resources(0.1, "2GiB"),
            dynamic_services_settings=dynamic_services_settings,
            egress_proxy_count=0,
            with_tracing=False,
            with_rclone=False,
            instance_cpus=2,
            instance_ram=TypeAdapter(ByteSize).validate_python("2GiB"),
        )
