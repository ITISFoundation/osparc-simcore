# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ByteSize, TypeAdapter
from servicelib.resources import USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY, USER_SERVICE_MEM_RESOURCE_LIMIT_ENV_KEY
from settings_library.egress_proxy import EgressProxySettings
from simcore_service_dynamic_sidecar.core._helper_container_resources import (
    NotEnoughResourcesForHelperContainersError,
    NoUserServiceFoundError,
    _compute_helper_containers_footprint,
    _deduct_helper_containers_resources,
    _find_biggest_overall_service,
    _get_biggest_user_service,
    _read_limits,
    _Resources,
    _write_limits,
    remove_helper_containers_resources,
)
from simcore_service_dynamic_sidecar.core.settings import HelperContainersResourceSettings

_MiB = TypeAdapter(ByteSize).validate_python("1MiB")
_GiB = TypeAdapter(ByteSize).validate_python("1GiB")
_NANO = 10**9


@pytest.fixture
def envoy_proxy_settings() -> EgressProxySettings:
    return EgressProxySettings.create_from_envs()


@pytest.fixture
def mocked_settings() -> MagicMock:
    settings = MagicMock()
    settings.DY_SIDECAR_HELPER_CONTAINERS_RESOURCE_SETTINGS = HelperContainersResourceSettings(
        DY_SIDECAR_HELPER_CONTAINERS_MIN_REMAINING_RESOURCE_FRACTION=0.48,
        DY_SIDECAR_RCLONE_MAX_SERVICE_RESOURCE_FRACTION=0.10,
    )
    return settings


def _service(
    cpu: float,
    ram_mib: int,
    cpu_reservation: float | None = None,
    ram_mib_reservation: int | None = None,
    *,
    inject_resource_limit_envs: bool = False,
) -> dict[str, Any]:
    limits: dict[str, Any] = {"cpus": f"{cpu}", "memory": f"{ram_mib * _MiB}"}
    reservations: dict[str, Any] = {
        "cpus": f"{cpu_reservation if cpu_reservation is not None else cpu}",
        "memory": f"{(ram_mib_reservation if ram_mib_reservation is not None else ram_mib) * _MiB}",
    }
    spec: dict[str, Any] = {"deploy": {"resources": {"limits": limits, "reservations": reservations}}}
    if inject_resource_limit_envs:
        # mirrors what director-v2 injects: original (pre-deduction) values
        spec["environment"] = [
            f"{USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY}={int(cpu * _NANO)}",
            f"{USER_SERVICE_MEM_RESOURCE_LIMIT_ENV_KEY}={ram_mib * _MiB}",
            "SOME_OTHER_ENV=unchanged",
        ]
    return spec


def _compose(services: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"services": services}


# ---- _read_limits / _write_limits -------------------------------------------


def test_read_limits_returns_cpu_and_ram():
    spec = _service(cpu=2.0, ram_mib=4096)
    r = _read_limits(spec)
    assert r.cpu == pytest.approx(2.0)
    assert r.ram == 4096 * _MiB


def test_read_limits_missing_deploy_returns_zeros():
    r = _read_limits({"image": "foo"})
    assert r.cpu == pytest.approx(0.0)
    assert r.ram == 0


def test_read_limits_compose_v2():
    spec = {"cpus": 2.0, "mem_limit": f"{4096 * _MiB}"}
    r = _read_limits(spec)
    assert r.cpu == pytest.approx(2.0)
    assert r.ram == 4096 * _MiB


def test_write_limits_updates_and_clamps_reservations():
    spec = _service(cpu=4.0, ram_mib=8192, cpu_reservation=4.0, ram_mib_reservation=8192)
    _write_limits(spec, _Resources(cpu=3.0, ram=4096 * _MiB))
    limits = spec["deploy"]["resources"]["limits"]
    reservations = spec["deploy"]["resources"]["reservations"]
    assert float(limits["cpus"]) == pytest.approx(3.0)
    assert int(limits["memory"]) == 4096 * _MiB
    # reservations must be clamped to new limit
    assert float(reservations["cpus"]) <= 3.0
    assert int(reservations["memory"]) <= 4096 * _MiB


def test_write_limits_updates_resource_limit_env_vars():
    """director-v2 injects SIMCORE_NANO_CPUS_LIMIT / SIMCORE_MEMORY_BYTES_LIMIT before the
    sidecar runs. After deduction those vars must reflect the *reduced* limits."""
    spec = _service(cpu=4.0, ram_mib=8192, inject_resource_limit_envs=True)
    _write_limits(spec, _Resources(cpu=3.0, ram=4096 * _MiB))

    env: dict[str, str] = dict(e.split("=", 1) for e in spec["environment"])
    assert int(env[USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY]) == int(3.0 * _NANO)
    assert int(env[USER_SERVICE_MEM_RESOURCE_LIMIT_ENV_KEY]) == 4096 * _MiB
    # unrelated env var must survive
    assert env["SOME_OTHER_ENV"] == "unchanged"


def test_write_limits_adds_env_vars_when_not_previously_set():
    """If director-v2 didn't inject the env vars (unusual path), _write_limits adds them."""
    spec = _service(cpu=4.0, ram_mib=8192)  # no environment key at all
    _write_limits(spec, _Resources(cpu=3.0, ram=4096 * _MiB))

    env: dict[str, str] = dict(e.split("=", 1) for e in spec["environment"])
    assert USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY in env
    assert USER_SERVICE_MEM_RESOURCE_LIMIT_ENV_KEY in env


def test_write_limits_compose_v2_updates_and_clamps_reservation():
    spec: dict[str, Any] = {
        "cpus": 4.0,
        "mem_limit": f"{8192 * _MiB}",
        "mem_reservation": f"{8192 * _MiB}",
    }
    _write_limits(spec, _Resources(cpu=3.0, ram=4096 * _MiB))
    assert spec["cpus"] == pytest.approx(3.0)
    assert int(spec["mem_limit"]) == 4096 * _MiB
    assert int(spec["mem_reservation"]) <= 4096 * _MiB


# ---- _find_biggest_overall_service ------------------------------------------


def test_find_biggest_service_by_ram_first():
    spec_services = {
        "svc-a": _service(cpu=4.0, ram_mib=2048),  # less RAM
        "svc-b": _service(cpu=2.0, ram_mib=8192),  # more RAM → wins
    }
    assert _find_biggest_overall_service(spec_services, list(spec_services)) == "svc-b"


def test_find_biggest_service_cpu_tiebreak():
    spec_services = {
        "svc-a": _service(cpu=4.0, ram_mib=4096),  # same RAM, more CPU → wins
        "svc-b": _service(cpu=2.0, ram_mib=4096),
    }
    assert _find_biggest_overall_service(spec_services, list(spec_services)) == "svc-a"


def test_find_biggest_service_single():
    spec_services = {"only": _service(cpu=1.0, ram_mib=1024)}
    assert _find_biggest_overall_service(spec_services, ["only"]) == "only"


# ---- _compute_helper_containers_footprint ----------------------------------


def _make_settings(
    egress: EgressProxySettings,
    *,
    cpu_limit: float = 0.25,
    ram_mib: int = 256,
    rclone_cpu_nano: int = int(1e9),
    rclone_ram_mib: int = 10240,
) -> MagicMock:
    tracing_cfg = MagicMock()
    tracing_cfg.USER_SERVICES_TRACING_COLLECTOR_CPU_LIMIT = cpu_limit
    tracing_cfg.USER_SERVICES_TRACING_COLLECTOR_MEMORY_LIMIT = ram_mib * _MiB

    mount_cfg = MagicMock()
    mount_cfg.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_NANO_CPUS = rclone_cpu_nano
    mount_cfg.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_MEMORY_LIMIT = rclone_ram_mib * _MiB

    rclone_settings = MagicMock()
    rclone_settings.R_CLONE_SIMCORE_SDK_MOUNT_SETTINGS = mount_cfg

    settings = MagicMock()
    settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING_CONFIG = tracing_cfg
    settings.DY_SIDECAR_R_CLONE_SETTINGS = rclone_settings
    settings.DY_SIDECAR_EGRESS_PROXY_SETTINGS = egress
    settings.DY_SIDECAR_HELPER_CONTAINERS_RESOURCE_SETTINGS = HelperContainersResourceSettings(
        DY_SIDECAR_RCLONE_MAX_SERVICE_RESOURCE_FRACTION=1.0,  # no cap in unit tests
    )
    return settings


_LARGE_SERVICE = _Resources(cpu=1000.0, ram=1000 * _GiB)  # reference used where capping must not trigger


def test_footprint_nothing_enabled(envoy_proxy_settings: EgressProxySettings):
    settings = _make_settings(envoy_proxy_settings)
    r, _ = _compute_helper_containers_footprint(
        settings, egress_proxy_count=0, with_tracing=False, with_rclone=False, biggest_service_resources=_LARGE_SERVICE
    )
    assert r.cpu == pytest.approx(0.0)
    assert r.ram == 0


def test_footprint_envoy_only(envoy_proxy_settings: EgressProxySettings):
    settings = _make_settings(envoy_proxy_settings)
    r, _ = _compute_helper_containers_footprint(
        settings, egress_proxy_count=1, with_tracing=False, with_rclone=False, biggest_service_resources=_LARGE_SERVICE
    )
    assert r.cpu == pytest.approx(envoy_proxy_settings.DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT)
    assert r.ram == int(envoy_proxy_settings.DYNAMIC_SIDECAR_ENVOY_MEMORY_LIMIT)


def test_footprint_multiple_envoy_proxies(envoy_proxy_settings: EgressProxySettings):
    settings = _make_settings(envoy_proxy_settings)
    r, _ = _compute_helper_containers_footprint(
        settings, egress_proxy_count=3, with_tracing=False, with_rclone=False, biggest_service_resources=_LARGE_SERVICE
    )
    assert r.cpu == pytest.approx(3 * envoy_proxy_settings.DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT)
    assert r.ram == 3 * int(envoy_proxy_settings.DYNAMIC_SIDECAR_ENVOY_MEMORY_LIMIT)


def test_footprint_tracing_counts_collector_and_forwarder(envoy_proxy_settings: EgressProxySettings):
    settings = _make_settings(envoy_proxy_settings, cpu_limit=0.25, ram_mib=256)
    r, _ = _compute_helper_containers_footprint(
        settings, egress_proxy_count=0, with_tracing=True, with_rclone=False, biggest_service_resources=_LARGE_SERVICE
    )
    assert r.cpu == pytest.approx(2 * 0.25)
    assert r.ram == 2 * 256 * _MiB


def test_footprint_all_enabled(envoy_proxy_settings: EgressProxySettings):
    settings = _make_settings(
        envoy_proxy_settings, cpu_limit=0.25, ram_mib=256, rclone_cpu_nano=int(1e9), rclone_ram_mib=10240
    )
    r, _ = _compute_helper_containers_footprint(
        settings, egress_proxy_count=1, with_tracing=True, with_rclone=True, biggest_service_resources=_LARGE_SERVICE
    )
    expected_cpu = envoy_proxy_settings.DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT + 2 * 0.25 + 1.0
    expected_ram = int(envoy_proxy_settings.DYNAMIC_SIDECAR_ENVOY_MEMORY_LIMIT) + 2 * 256 * _MiB + 10240 * _MiB
    assert r.cpu == pytest.approx(expected_cpu)
    assert r.ram == expected_ram


def test_footprint_rclone_capped_by_service_fraction(envoy_proxy_settings: EgressProxySettings):
    """rclone allocation is capped at DY_SIDECAR_RCLONE_MAX_SERVICE_RESOURCE_FRACTION of the service."""
    max_fraction = 0.10
    service = _Resources(cpu=4.0, ram=8192 * _MiB)
    settings = _make_settings(envoy_proxy_settings, rclone_cpu_nano=int(4e9), rclone_ram_mib=8192)
    settings.DY_SIDECAR_HELPER_CONTAINERS_RESOURCE_SETTINGS = HelperContainersResourceSettings(
        DY_SIDECAR_RCLONE_MAX_SERVICE_RESOURCE_FRACTION=max_fraction,
    )
    r, _ = _compute_helper_containers_footprint(
        settings, egress_proxy_count=0, with_tracing=False, with_rclone=True, biggest_service_resources=service
    )
    assert r.cpu == pytest.approx(service.cpu * max_fraction)
    assert r.ram == int(service.ram * max_fraction)


def test_footprint_description_lists_active_helpers(envoy_proxy_settings: EgressProxySettings):
    settings = _make_settings(envoy_proxy_settings)
    _, desc = _compute_helper_containers_footprint(
        settings, egress_proxy_count=2, with_tracing=True, with_rclone=True, biggest_service_resources=_LARGE_SERVICE
    )
    assert "envoy x2" in desc
    assert "otel collector+forwarder" in desc
    assert "rclone" in desc


def test_footprint_description_empty_when_nothing_enabled(envoy_proxy_settings: EgressProxySettings):
    settings = _make_settings(envoy_proxy_settings)
    _, desc = _compute_helper_containers_footprint(
        settings, egress_proxy_count=0, with_tracing=False, with_rclone=False, biggest_service_resources=_LARGE_SERVICE
    )
    assert desc == ""


# ---- _deduct_helper_containers_resources: success path ---------------------


def test_deduct_subtracts_from_biggest(mocked_settings: MagicMock):
    compose = _compose(
        {
            "svc-small": _service(cpu=2.0, ram_mib=2048, inject_resource_limit_envs=True),
            "svc-big": _service(cpu=4.0, ram_mib=8192, inject_resource_limit_envs=True),
        }
    )
    name, resources = _get_biggest_user_service(compose)
    helpers_resources = _Resources(cpu=1.0, ram=1024 * _MiB)
    _deduct_helper_containers_resources(
        mocked_settings,
        compose,
        biggest_service_name=name,
        biggest_service_resources=resources,
        helpers_resources=helpers_resources,
        helpers_desc="test",
    )

    big_limits = _read_limits(compose["services"]["svc-big"])
    small_limits = _read_limits(compose["services"]["svc-small"])

    assert big_limits.cpu == pytest.approx(3.0)
    assert big_limits.ram == 7168 * _MiB
    # small service is untouched
    assert small_limits.cpu == pytest.approx(2.0)
    assert small_limits.ram == 2048 * _MiB


def test_deduct_clamps_reservations(mocked_settings: MagicMock):
    compose = _compose(
        {
            "svc": _service(
                cpu=4.0,
                ram_mib=8192,
                cpu_reservation=4.0,
                ram_mib_reservation=8192,
                inject_resource_limit_envs=True,
            ),
        }
    )
    name, resources = _get_biggest_user_service(compose)
    helpers_resources = _Resources(cpu=1.0, ram=1024 * _MiB)
    _deduct_helper_containers_resources(
        mocked_settings,
        compose,
        biggest_service_name=name,
        biggest_service_resources=resources,
        helpers_resources=helpers_resources,
        helpers_desc="test",
    )

    spec = compose["services"]["svc"]
    reservations = spec["deploy"]["resources"]["reservations"]
    assert float(reservations["cpus"]) <= 3.0
    assert int(reservations["memory"]) <= 7168 * _MiB

    # env vars must also reflect post-deduction values
    env: dict[str, str] = dict(e.split("=", 1) for e in spec["environment"])
    assert int(env[USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY]) == int(3.0 * _NANO)
    assert int(env[USER_SERVICE_MEM_RESOURCE_LIMIT_ENV_KEY]) == 7168 * _MiB


def test_raises_when_no_user_services(mocked_settings: MagicMock):
    # service without SIMCORE_NANO_CPUS_LIMIT is treated as a helper — raises
    compose = _compose({"helper-svc": _service(cpu=2.0, ram_mib=2048)})
    with pytest.raises(NoUserServiceFoundError):
        _get_biggest_user_service(compose)


# ---- _deduct_helper_containers_resources: hard floor (<=0) -----------------


@pytest.mark.parametrize(
    "helpers_resources",
    [
        pytest.param(_Resources(cpu=5.0, ram=512 * _MiB), id="cpu_exceeds_limit"),
        pytest.param(_Resources(cpu=1.0, ram=10 * _GiB), id="ram_exceeds_limit"),
        pytest.param(_Resources(cpu=4.0, ram=8192 * _MiB), id="both_exactly_zero"),
    ],
)
def test_deduct_raises_hard_floor(helpers_resources: _Resources, mocked_settings: MagicMock):
    compose = _compose({"svc": _service(cpu=4.0, ram_mib=8192, inject_resource_limit_envs=True)})
    name, resources = _get_biggest_user_service(compose)
    with pytest.raises(NotEnoughResourcesForHelperContainersError):
        _deduct_helper_containers_resources(
            mocked_settings,
            compose,
            biggest_service_name=name,
            biggest_service_resources=resources,
            helpers_resources=helpers_resources,
            helpers_desc="test",
        )


# ---- _deduct_helper_containers_resources: soft floor (<48%) ----------------


@pytest.mark.parametrize(
    "helpers_resources",
    [
        # leaves only 40% CPU (< 48%)
        pytest.param(_Resources(cpu=2.4, ram=100 * _MiB), id="cpu_below_48pct"),
        # leaves only 40% RAM (< 48%)
        pytest.param(_Resources(cpu=0.1, ram=int(8192 * _MiB * 0.61)), id="ram_below_48pct"),
    ],
)
def test_deduct_raises_soft_floor(helpers_resources: _Resources, mocked_settings: MagicMock):
    compose = _compose({"svc": _service(cpu=4.0, ram_mib=8192, inject_resource_limit_envs=True)})
    name, resources = _get_biggest_user_service(compose)
    with pytest.raises(NotEnoughResourcesForHelperContainersError):
        _deduct_helper_containers_resources(
            mocked_settings,
            compose,
            biggest_service_name=name,
            biggest_service_resources=resources,
            helpers_resources=helpers_resources,
            helpers_desc="test",
        )


def test_deduct_exactly_at_48pct_passes(mocked_settings: MagicMock):
    """A remaining fraction exactly equal to the configured minimum must NOT raise."""
    resource_settings = mocked_settings.DY_SIDECAR_HELPER_CONTAINERS_RESOURCE_SETTINGS
    min_fraction = resource_settings.DY_SIDECAR_HELPER_CONTAINERS_MIN_REMAINING_RESOURCE_FRACTION
    original_cpu = 4.0
    original_ram = 8192 * _MiB
    # subtract exactly (1 - min_fraction) so that min_fraction remains
    helpers_resources = _Resources(cpu=original_cpu * (1 - min_fraction), ram=int(original_ram * (1 - min_fraction)))
    compose = _compose({"svc": _service(cpu=original_cpu, ram_mib=8192, inject_resource_limit_envs=True)})
    name, resources = _get_biggest_user_service(compose)
    _deduct_helper_containers_resources(
        mocked_settings,
        compose,
        biggest_service_name=name,
        biggest_service_resources=resources,
        helpers_resources=helpers_resources,
        helpers_desc="test",
    )
    r = _read_limits(compose["services"]["svc"])
    assert r.cpu == pytest.approx(original_cpu * min_fraction, rel=1e-6)
    assert r.ram == pytest.approx(original_ram * min_fraction, rel=1e-6)


# ---- remove_helper_containers_resources -------------------------------------


def test_remove_noop_when_no_helpers(mocked_settings: MagicMock):
    """With zero helper containers requested the limits are unchanged."""
    compose = _compose({"svc": _service(cpu=4.0, ram_mib=8192, inject_resource_limit_envs=True)})
    remove_helper_containers_resources(
        mocked_settings, compose, egress_proxy_count=0, with_tracing=False, with_rclone=False
    )
    r = _read_limits(compose["services"]["svc"])
    assert r.cpu == pytest.approx(4.0)
    assert r.ram == 8192 * _MiB


def test_remove_raises_when_no_user_services(mocked_settings: MagicMock):
    compose = _compose({"helper-svc": _service(cpu=2.0, ram_mib=2048)})
    with pytest.raises(NoUserServiceFoundError):
        remove_helper_containers_resources(
            mocked_settings, compose, egress_proxy_count=0, with_tracing=False, with_rclone=False
        )


def test_remove_propagates_not_enough_resources_error(mocked_settings: MagicMock):
    """Requesting more helpers than the service can accommodate raises through remove_*."""
    compose = _compose({"svc": _service(cpu=4.0, ram_mib=8192, inject_resource_limit_envs=True)})
    # inject a fake egress_proxy_count that will consume the entire service allocation
    mocked_settings.DY_SIDECAR_EGRESS_PROXY_SETTINGS.DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT = 4.0
    mocked_settings.DY_SIDECAR_EGRESS_PROXY_SETTINGS.DYNAMIC_SIDECAR_ENVOY_MEMORY_LIMIT = 8192 * _MiB
    with pytest.raises(NotEnoughResourcesForHelperContainersError):
        remove_helper_containers_resources(
            mocked_settings, compose, egress_proxy_count=1, with_tracing=False, with_rclone=False
        )
