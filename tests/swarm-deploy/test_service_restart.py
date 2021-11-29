# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
import time
from pprint import pformat
from typing import List

import pytest
from docker.models.services import Service

log = logging.getLogger(__name__)


SERVICES_AND_EXIT_CODES = [
    # SEE https://betterprogramming.pub/understanding-docker-container-exit-codes-5ee79a1d58f6
    ("api-server", 0),
    ("catalog", 0),
    ("dask-sidecar", 0),
    ("datcore-adapter", 0),
    ("director-v2", 0),
    ("migration", 143),
    ("static-webserver", 15),
    ("storage", 0),
    ("webserver", 0),
]

MAX_TIME_TO_RESTART_SERVICE = 10

# FIXME: https://github.com/ITISFoundation/osparc-simcore/issues/2407
@pytest.mark.skip(
    reason="UNDER INVESTIGATION: unclear why this test affects the state of others."
    "It works locally but not online."
)
@pytest.mark.parametrize(
    "docker_compose_service_key,exit_code",
    SERVICES_AND_EXIT_CODES,
    ids=[f"service={x[0]},exit_code={x[1]}" for x in SERVICES_AND_EXIT_CODES],
)
def test_graceful_restart_services(
    simcore_stack_deployed_services: List[Service],
    docker_compose_service_key: str,
    exit_code: int,
):
    """
        This tests ensures that the applications running in the service above
        can be properly restarted.

        It force update the service even if no changes requires it (i.e "docker service update --force" ).
        which will recreate the task. It is expected that the app process inside
        handles properly the signal and shutsdown gracefuly returning statuscode 0.


    Did this case FAILED? These are the typical reasons:

    Check good practices:
        - use exec form for ENTRYPOINT in Dockerfile, i.e ["executable", "arg1", "arg2"]
        - if entrypoint is a shell-script, then exec the app
        - start docker with tini as PID1, i.e. docker run with --init
        - use gosu utility in ENTRYPOINT instead of sudo/su

    GOOD References worth reading to understand this topic:
        https://blog.container-solutions.com/6-dockerfile-tips-official-images
        https://hynek.me/articles/docker-signals/
        https://kkc.github.io/2018/06/06/gracefully-shutdown-docker-container/
        https://docs.docker.com/develop/develop-images/dockerfile_best-practices/

    SEE Gracefully Stopping Docker Containers by DeHamer: https://www.ctl.io/developers/blog/post/gracefully-stopping-docker-containers/
    SEE Gracefully Shutdown Docker Container by Kakashi: https://kkc.github.io/2018/06/06/gracefully-shutdown-docker-container/

    """
    assert simcore_stack_deployed_services

    assert any(
        s.name.endswith(docker_compose_service_key)
        for s in simcore_stack_deployed_services
    )

    # Service names:'pytest-simcore_static-webserver', 'pytest-simcore_webserver'
    service: Service = next(
        s
        for s in simcore_stack_deployed_services
        if s.name.endswith(f"_{docker_compose_service_key}")
    )

    # NOTE: This is how it looks status. Do not delete
    # "Status": {
    #     "Timestamp": "2019-11-18T19:33:30.448132327Z",
    #     "State": "shutdown",
    #     "Message": "shutdown",
    #     "ContainerStatus": {
    #         "ContainerID": "f2921c983ad934b4daa0c514543bbfd1a9ea89189bd1ad98b67d63b9f98f05be",
    #         "PID": 0,
    #         "ExitCode": 143
    #     },
    #     "PortStatus": {}
    # },
    # "DesiredState": "shutdown",
    assert all(task["Status"]["State"] == "running" for task in service.tasks())

    assert service.force_update()

    time.sleep(MAX_TIME_TO_RESTART_SERVICE)

    shutdown_tasks = service.tasks(filters={"desired-state": "shutdown"})
    assert len(shutdown_tasks) == 1

    task = shutdown_tasks[0]
    assert task["Status"]["ContainerStatus"]["ExitCode"] == exit_code, (
        f"{docker_compose_service_key} expected exit_code=={exit_code}; "
        f"got task_status={pformat(task['Status'])}"
    )

    # TODO: check ps ax has TWO processes
    ## name = core_service_name.name.replace("simcore_", "")
    ## cmd = f"docker exec -it $(docker ps | grep {name} | awk '{{print $1}}') /bin/sh -c 'ps ax'"
    # $ docker exec -it $(docker ps | grep storage | awk '{print $1}') /bin/sh -c 'ps ax'
    # PID   USER     TIME  COMMAND
    #   1 root      0:00 /sbin/docker-init -- /bin/sh services/storage/docker/entry
    #   6 scu       0:02 {simcore-service} /usr/local/bin/python /usr/local/bin/sim
    #  54 root      0:00 ps ax

    # $ docker exec -it $(docker ps | grep sidecar | awk '{print $1}') /bin/sh -c 'ps ax'
    # PID   USER     TIME  COMMAND
    #  1 root      0:00 /sbin/docker-init -- /bin/sh services/sidecar/docker/entry
    #  6 scu       0:00 {celery} /usr/local/bin/python /usr/local/bin/celery worke
    # 26 scu       0:00 {celery} /usr/local/bin/python /usr/local/bin/celery worke
    # 27 scu       0:00 {celery} /usr/local/bin/python /usr/local/bin/celery worke
