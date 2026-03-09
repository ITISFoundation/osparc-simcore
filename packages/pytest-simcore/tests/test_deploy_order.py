from pathlib import Path

from pytest_simcore.docker_swarm import _get_compose_service_order

_SERVICES_DEPLOY_ORDER: list[str] = [
    "postgres",
    "migration",
    "redis",
    "rabbit",
    "director",
    # above are required for other services to run
    "catalog",
    "agent",
    "docker-api-proxy",
    "static-webserver",
    "storage",
    "sto-worker",
    "sto-worker-cpu-bound",
    "dask-sidecar",
    "dask-scheduler",
    "director-v2",
    "dynamic-schdlr",
    "webserver",
    "wb-garbage-collector",
    "wb-api-server",
    "wb-auth",
    "wb-db-event-listener",
    "autoscaling",
    "clusters-keeper",
    "resource-usage-tracker",
    "efs-guardian",
    "api-server",
    "api-worker",
    "datcore-adapter",
    "invitations",
    "notifications",
    "notifications-worker",
    "payments",
    "traefik-config-placeholder",
    "traefik",
]


def test_appears_in_sequence(osparc_simcore_root_dir: Path):
    compose_services = _get_compose_service_order(osparc_simcore_root_dir)

    # Every service in the deploy order must exist in docker-compose
    missing = [s for s in _SERVICES_DEPLOY_ORDER if s not in compose_services]
    assert not missing, f"Services in deploy order not found in docker-compose: {missing}"

    assert len(_SERVICES_DEPLOY_ORDER) == len(compose_services), (
        "Number of services in deploy order does not match number of services in docker-compose. "
        "Check for missing or extra services."
    )

    # The relative order of services as they appear in docker-compose must match
    # the order defined in _SERVICES_DEPLOY_ORDER
    positions = [compose_services.index(s) for s in _SERVICES_DEPLOY_ORDER]
    assert positions == sorted(positions), (
        "Services in _SERVICES_DEPLOY_ORDER are not in the same relative order "
        "as they appear in docker-compose.yml.\n"
        "Expected order (by docker-compose position):\n"
        + "\n".join(f"  {compose_services[p]} (pos {p})" for p in sorted(positions))
    )
