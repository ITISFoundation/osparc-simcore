import json

import arrow
import requests
from models import RunningSidecar
from settings import Settings


def get_bearer_token(settings: Settings):
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
    bearer_token = response.json()["jwt"]
    return bearer_token


def get_services(settings: Settings, bearer_token):
    services_url = f"{settings.portainer_url}/portainer/api/endpoints/{settings.portainer_endpoint_version}/docker/services"
    response = requests.get(
        services_url,
        headers={
            "Authorization": "Bearer " + bearer_token,
            "Content-Type": "application/json",
        },
    )
    services = response.json()
    return services


def get_tasks(settings: Settings, bearer_token):
    tasks_url = f"{settings.portainer_url}/portainer/api/endpoints/{settings.portainer_endpoint_version}/docker/tasks"
    response = requests.get(
        tasks_url,
        headers={
            "Authorization": "Bearer " + bearer_token,
            "Content-Type": "application/json",
        },
    )
    tasks = response.json()
    return tasks


def get_containers(settings: Settings, bearer_token):
    bearer_token = get_bearer_token(settings)

    containers_url = f"{settings.portainer_url}/portainer/api/endpoints/{settings.portainer_endpoint_version}/docker/containers/json?all=true"
    response = requests.get(
        containers_url,
        headers={
            "Authorization": "Bearer " + bearer_token,
            "Content-Type": "application/json",
        },
    )
    containers = response.json()
    return containers


def check_simcore_running_sidecars(settings: Settings, services):
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
        container_map[container["Id"]] = {
            "git_sha": container.get("Labels").get("org.label-schema.vcs-ref")
        }
    return container_map


def check_simcore_deployed_services(settings: Settings, services, tasks, containers):
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
