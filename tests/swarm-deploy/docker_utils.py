"""


 Swarm task states:
    https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/

 Lifecyle of Docker Container:
    https://medium.com/@nagarwal/lifecycle-of-docker-container-d2da9f85959
    http://docker-saigon.github.io/post/Docker-Internals/#docker-api:cb6baf67dddd3a71c07abfd705dc7d4b
"""
import re
from collections import OrderedDict
from enum import Enum
from pprint import pformat
from textwrap import dedent
from timeit import default_timer
from typing import Callable

import docker
from tenacity import Retrying, stop_after_delay

TASK_STATE_DESCRIPTION = OrderedDict([ re.split(r'\s+', entry, 1) for entry in dedent("""
NEW       The task was initialized.
PENDING   Resources for the task were allocated.
ASSIGNED  Docker assigned the task to nodes.
ACCEPTED  The task was accepted by a worker node. If a worker node rejects the task, the state changes to REJECTED.
PREPARING Docker is preparing the task.
STARTING  Docker is starting the task.
RUNNING   The task is executing.
COMPLETE  The task exited without an error code.
FAILED    The task exited with an error code.
SHUTDOWN  Docker requested the task to shut down.
REJECTED  The worker node rejected the task.
ORPHANED  The node was down for too long.
REMOVE    The task is not terminal but the associated service was removed or scaled down.
""").strip().split('\n') ])

TaskState = Enum("TaskState", list(TASK_STATE_DESCRIPTION.keys()))


failed_states = [
    TaskState.COMPLETE,
    TaskState.FAILED,
    TaskState.SHUTDOWN,
    TaskState.REJECTED,
    TaskState.ORPHANED,
    TaskState.REMOVE,
    TaskState.CREATED
]




def assert_all_services_ready(filters=None):
    """ All tasks reach desired state

        Docker lets you create services, which can start tasks.
        A service is a description of a **desired state**, and a task does the work

    SEE Swarm stak states https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/
    """
    docker_client = docker.from_env()
    for service in docker_client.services.list(filters=filters):
        for task in service.tasks():
            assert task['Status']['State'] == task['DesiredState'], \
                f'{service.name} still not ready: {pformat(task)}'


def eval_time_elapsed(assert_fun: Callable, max_timeout_secs=120):
    start = default_timer()

    for attempt in Retrying(stop=stop_after_delay(max_timeout_secs)):
        with attempt:
            assert_fun()

    end = default_timer()
    elapsed_secs = end - start
    print("Time elapsed [secs]  ", elapsed_secs) # Time in seconds, e.g. 5.38091952400282
    return elapsed_secs
