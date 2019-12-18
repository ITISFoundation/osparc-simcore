# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import subprocess
import time
from pathlib import Path

import docker
import pytest
import yaml


@pytest.fixture(scope='session')
def docker_client():
    client = docker.from_env()
    yield client

@pytest.fixture(scope='module')
def docker_swarm(docker_client):
    docker_client.swarm.init()
    yield
    # teardown
    assert docker_client.swarm.leave(force=True)


@pytest.fixture(scope='module')
def docker_stack(docker_swarm, docker_client, core_services_config_file: Path, ops_services_config_file: Path):
    stacks = {
        'simcore': core_services_config_file,
        'ops': ops_services_config_file
    }

    # make up-version
    stacks_up = []
    for stack_name, stack_config_file in stacks.items():
        subprocess.run( f"docker stack deploy -c {stack_config_file.name} {stack_name}",
            shell=True, check=True,
            cwd=stack_config_file.parent)
        stacks_up.append(stack_name)

    # wait for the stack to come up
    def _wait_for_services(retry_count, max_wait_time_s):
        pre_states = [
            "NEW",
            "PENDING",
            "ASSIGNED",
            "PREPARING",
            "STARTING"
        ]
        services = docker_client.services.list()
        WAIT_TIME_BEFORE_RETRY = 5
        start_time = time.time()
        for service in services:
            for n in range(retry_count):
                assert (time.time() - start_time) < max_wait_time_s
                task = service.tasks()[0]
                if task["Status"]["State"].upper() in pre_states:
                    print(f"Waiting for {service.name}...")
                else:
                    assert task["Status"]["State"].upper() == "RUNNING"
                    break
                time.sleep(WAIT_TIME_BEFORE_RETRY)


    def _print_services(msg):
        from pprint import pprint
        print("{:*^100}".format("docker services running " + msg))
        for service in docker_client.services.list():
            pprint(service.attrs)
        print("-"*100)
    RETRY_COUNT = 12
    WAIT_TIME_BEFORE_FAILING = 60
    _wait_for_services(RETRY_COUNT, WAIT_TIME_BEFORE_FAILING)
    _print_services("[BEFORE TEST]")

    yield {
        'stacks': stacks_up,
        'services': [service.name for service in docker_client.services.list()]
    }

    _print_services("[AFTER TEST]")

    # clean up. Guarantees that all services are down before creating a new stack!
    #
    # WORKAROUND https://github.com/moby/moby/issues/30942#issue-207070098
    #
    # docker stack rm services

    # until [ -z "$(docker service ls --filter label=com.docker.stack.namespace=services -q)" ] || [ "$limit" -lt 0 ]; do
    # sleep 1;
    # done

    # until [ -z "$(docker network ls --filter label=com.docker.stack.namespace=services -q)" ] || [ "$limit" -lt 0 ]; do
    # sleep 1;
    # done

    # make down
    # NOTE: remove them in reverse order since stacks share common networks
    WAIT_BEFORE_RETRY_SECS = 1
    stacks_up.reverse()
    for stack in stacks_up:
        subprocess.run(f"docker stack rm {stack}", shell=True, check=True)

        while docker_client.services.list(filters={"label":f"com.docker.stack.namespace={stack}"}):
            time.sleep(WAIT_BEFORE_RETRY_SECS)

        while docker_client.networks.list(filters={"label":f"com.docker.stack.namespace={stack}"}):
            time.sleep(WAIT_BEFORE_RETRY_SECS)

    _print_services("[AFTER REMOVED]")
