#pylint: disable=unused-argument, unused-import
import pytest

from utils import create_tables, setup_sleepers

class FakeRequest():
    def __init__(self):
        self.id = "1"

class FakeTask():
    def __init__(self):
        self.request = FakeRequest()
        self.state = 0

    def update_state(self, state):
        self.state = state


def run(task, pipeline_id, node_id=None):
    next_task_nodes = []
    try:
        from sidecar.core import SIDECAR
        next_task_nodes = SIDECAR.inspect(task, pipeline_id, node_id)
    #pylint:disable=broad-except
    except Exception:
        assert False

    for _node_id in next_task_nodes:
        task.request.id = str(int(task.request.id) + 1)
        run(task, pipeline_id, _node_id)


def test_sleeper(sidecar_platform_fixture, postgres_service_url):
    # create database tables
    create_tables(postgres_service_url)

    # create entry for sleeper

    pipeline_id = setup_sleepers(postgres_service_url)
    task = FakeTask()

    run(task, pipeline_id, node_id=None)
