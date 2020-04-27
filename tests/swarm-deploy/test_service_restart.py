# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from pprint import pformat
from typing import Dict, List

import pytest
from tenacity import before_log, retry, stop_after_attempt, wait_fixed

from docker import DockerClient
from docker.models.services import Service

logger = logging.getLogger(__name__)

current_dir =  Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


# time measured from command 'up' finished until *all* tasks are running
MAX_TIME_TO_DEPLOY_SECS = 60
MAX_TIME_TO_RESTART_SERVICE = 10


@pytest.fixture("module")
def deployed_simcore_stack(make_up_prod: Dict, docker_client: DockerClient) -> List[Service]:
    # NOTE: the goal here is NOT to test time-to-deplopy but
    # rather guaranteing that the framework is fully deployed before starting
    # tests. Obviously in a critical state in which the frameworks has a problem
    # the fixture will fail
    STACK_NAME = 'simcore'
    assert STACK_NAME in make_up_prod

    @retry( wait=wait_fixed(MAX_TIME_TO_DEPLOY_SECS),
            stop=stop_after_attempt(5),
            before=before_log(logger, logging.WARNING) )
    def ensure_deployed():
        for service in docker_client.services.list():
            for task in service.tasks():
                assert task['Status']['State'] == task['DesiredState'], \
                    f'{service.name} still not ready: {pformat(task)}'

    try:
        ensure_deployed()
    finally:
        # logs table like
        #  ID                  NAME                  IMAGE                                      NODE                DESIRED STATE       CURRENT STATE                ERROR
        # xbrhmaygtb76        simcore_sidecar.1     itisfoundation/sidecar:latest              crespo-wkstn        Running             Running 53 seconds ago
        # zde7p8qdwk4j        simcore_rabbit.1      itisfoundation/rabbitmq:3.8.0-management   crespo-wkstn        Running             Running 59 seconds ago
        # f2gxmhwq7hhk        simcore_postgres.1    postgres:10.10                             crespo-wkstn        Running             Running about a minute ago
        # 1lh2hulxmc4q        simcore_director.1    itisfoundation/director:latest             crespo-wkstn        Running             Running 34 seconds ago
        # ...
        subprocess.run(f"docker stack ps {STACK_NAME}", shell=True, check=False)

    return [service for service in docker_client.services.list()
        if service.name.startswith(f"{STACK_NAME}_")]

#FIXME: @crespov, you need to fix this.
@pytest.mark.skipif(os.environ.get('GITHUB_ACTIONS', '') == "true", reason="test fails consistently on Github Actions")
@pytest.mark.parametrize("service_name", [
    'simcore_webserver',
    'simcore_storage',
    'simcore_catalog',
    'simcore_director',
])
def test_graceful_restart_services(
    service_name: str,
    deployed_simcore_stack: List[Service],
    make_up_prod: Dict):
    """
        This tests ensures that the applications running in the service above
        can be properly restarted.
        The test sends a kill signal and expects the app process inside to
        receive it and shut-down gracefuly returning statuscode 0.

        NOTE: needs to run AFTER test_core_service_running


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

    """
    service = next( s for s in deployed_simcore_stack if s.name == service_name )

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
    assert all( task['Status']['State'] == "running" for task in service.tasks() )

    assert service.force_update()

    time.sleep(MAX_TIME_TO_RESTART_SERVICE)

    shutdown_tasks = service.tasks(filters={'desired-state': 'shutdown'})
    assert len(shutdown_tasks) == 1

    task = shutdown_tasks[0]
    assert task['Status']['ContainerStatus']['ExitCode'] == 0, pformat(task['Status'])

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
