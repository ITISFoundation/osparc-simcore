import logging

import pytest

# Selection of core and tool services started in this swarm fixture (integration)
core_services = ["storage", "postgres", "rabbit"]

ops_services = ["minio", "adminer"]



async def test_run_sleepers(loop, docker_stack, postgres_session, sleeper_service, celery_service):
    import pdb
    pdb.set_trace()
    # next_task_nodes = await SIDECAR.inspect(task, user_id, pipeline_id, node_id)
