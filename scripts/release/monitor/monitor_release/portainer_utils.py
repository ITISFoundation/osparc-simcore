import json

import arrow
import requests
from monitor_release.models import RunningSidecar
from monitor_release.settings import LegacySettings


def get_bearer_token(settings: LegacySettings):
    headers = {"accept": "application/json", "Content-Type": "application/json"}
    payload = json.dumps(
        {
            "Username": settings.portainer_username,
            "Password": settings.portainer_password,
        }
    )
    response = requests.post(
        f"{settings.portainer_url}/portainer/api/auth",
        headers=headers,
        data=payload,
    )
    return response.json()["jwt"]


def get_services(settings: LegacySettings, bearer_token):
    services_url = f"{settings.portainer_url}/portainer/api/endpoints/{settings.portainer_endpoint_version}/docker/services"
    response = requests.get(
        services_url,
        headers={
            "Authorization": "Bearer " + bearer_token,
            "Content-Type": "application/json",
        },
    )
    return response.json()


def get_tasks(settings: LegacySettings, bearer_token):
    tasks_url = f"{settings.portainer_url}/portainer/api/endpoints/{settings.portainer_endpoint_version}/docker/tasks"
    response = requests.get(
        tasks_url,
        headers={
            "Authorization": "Bearer " + bearer_token,
            "Content-Type": "application/json",
        },
    )
    return response.json()


def get_containers(settings: LegacySettings, bearer_token):
    bearer_token = get_bearer_token(settings)

    containers_url = f"{settings.portainer_url}/portainer/api/endpoints/{settings.portainer_endpoint_version}/docker/containers/json?all=true"
    response = requests.get(
        containers_url,
        headers={
            "Authorization": "Bearer " + bearer_token,
            "Content-Type": "application/json",
        },
    )
    return response.json()


def check_simcore_running_sidecars(settings: LegacySettings, services):
    running_sidecars: list[RunningSidecar] = []
    for service in services:
        if (
            service["Spec"]["Name"].startswith("dy-sidecar")
            and service["Spec"]["Labels"]["io.simcore.runtime.swarm-stack-name"]
            == settings.swarm_stack_name
        ):
            running_sidecars.append(
                RunningSidecar(
                    name=service["Spec"]["Name"],
                    created_at=arrow.get(service["CreatedAt"]).datetime,
                    user_id=service["Spec"]["Labels"]["io.simcore.runtime.user-id"],
                    project_id=service["Spec"]["Labels"][
                        "io.simcore.runtime.project-id"
                    ],
                    service_key=service["Spec"]["Labels"][
                        "io.simcore.runtime.service-key"
                    ],
                    service_version=service["Spec"]["Labels"][
                        "io.simcore.runtime.service-version"
                    ],
                )
            )
    return running_sidecars


def _generate_containers_map(containers):
    container_map = {}
    for container in containers:
        git_sha = (
            container.get("Labels").get("org.opencontainers.image.revision")
            if container.get("Labels").get(
                "org.opencontainers.image.revision"
            )  # container.get("Labels").get("org.label-schema.vcs-ref")
            else container.get("Labels").get("org.label-schema.vcs-ref")
        )

        container_map[container["Id"]] = {"git_sha": git_sha}
    return container_map


def check_simcore_deployed_services(
    settings: LegacySettings, services, tasks, containers
):
    container_map = _generate_containers_map(containers)
    service_task_map = {}
    for service in services:
        if service["Spec"]["Name"].startswith(settings.starts_with):
            service_task_map[service["ID"]] = {
                "service_name": service["Spec"]["Name"],
                "tasks": [],
            }

    for task in tasks:
        if task["ServiceID"] in service_task_map:
            if task["Status"].get("ContainerStatus") is None:
                continue
            container_id = task["Status"]["ContainerStatus"]["ContainerID"]

            service_task_map[task["ServiceID"]]["tasks"].append(
                {
                    "created_at": arrow.get(task["CreatedAt"]).datetime,
                    "status": task["Status"]["State"],
                    "timestamp": arrow.get(task["Status"]["Timestamp"]).datetime,
                    "git_sha": container_map.get(container_id, {}).get("git_sha"),
                }
            )

    return service_task_map
