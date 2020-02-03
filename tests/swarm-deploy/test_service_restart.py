# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import subprocess
import sys
import time
from pathlib import Path
from pprint import pformat
from typing import Dict, List

import pytest
from docker import DockerClient
from docker.models.services import Service
from tenacity import Retrying, before_log, stop_after_attempt, wait_fixed

from docker_utils import assert_all_services_ready

logger = logging.getLogger(__name__)

current_dir =  Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


# time measured from command 'up' finished until *all* tasks are running
MAX_TIME_TO_DEPLOY_SECS = 60
MAX_TIME_TO_RESTART_SERVICE_SECS = 5

# FIXME: how to compute these times? Measure in dev computer and extrapolate based on testing machines?
# TODO: routines to "tune" these times and how can we see evolution?
#  - testing timing with respect to release version?? test it cannot be slower than released version?


@pytest.fixture("module")
def deployed_simcore_stack(osparc_deploy: Dict, docker_client: DockerClient) -> List[Service]:
    # NOTE: the goal here is NOT to test time-to-deplopy but
    # rather guaranteing that the framework is fully deployed before starting
    # tests. Obviously in a critical state in which the frameworks has a problem
    # the fixture will fail
    try:
        for attempt in Retrying(wait=wait_fixed(MAX_TIME_TO_DEPLOY_SECS),
                                stop=stop_after_attempt(5),
                                before=before_log(logger, logging.WARNING)):
            with attempt:
                assert_all_services_ready()
    finally:
        # logs table like
        #  ID                  NAME                  IMAGE                                      NODE                DESIRED STATE       CURRENT STATE                ERROR
        # xbrhmaygtb76        simcore_sidecar.1     itisfoundation/sidecar:latest              crespo-wkstn        Running             Running 53 seconds ago
        # zde7p8qdwk4j        simcore_rabbit.1      itisfoundation/rabbitmq:3.8.0-management   crespo-wkstn        Running             Running 59 seconds ago
        # f2gxmhwq7hhk        simcore_postgres.1    postgres:10.10                             crespo-wkstn        Running             Running about a minute ago
        # 1lh2hulxmc4q        simcore_director.1    itisfoundation/director:latest             crespo-wkstn        Running             Running 34 seconds ago
        # ...
        subprocess.run(f"docker stack ps simcore", shell=True, check=False)

    return docker_client.services.list(filters={'name':'simcore'})


@pytest.mark.parametrize("service_name", [
    'simcore_webserver',
    'simcore_storage'
])
def test_graceful_restart_services(
    service_name: str,
    deployed_simcore_stack: List[Service],
    osparc_deploy: Dict):
    """
        NOTE: loop fixture makes this test async
        NOTE: needs to run AFTER test_core_service_running

        SEE Gracefully Stopping Docker Containers by DeHamer: https://www.ctl.io/developers/blog/post/gracefully-stopping-docker-containers/
        SEE Gracefully Shutdown Docker Container by Kakashi: https://kkc.github.io/2018/06/06/gracefully-shutdown-docker-container/
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

    time.sleep(MAX_TIME_TO_RESTART_SERVICE_SECS)

    shutdown_tasks = service.tasks(filters={'desired-state': 'shutdown'})
    assert len(shutdown_tasks) == 1

    task = shutdown_tasks[0]
    assert task['Status']['ContainerStatus']['ExitCode'] == 0, \
        pformat(task['Status']) + f"\nLOGS:\n{pformat(list( service.logs() ))}\n"

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
