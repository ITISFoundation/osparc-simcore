# pylint: disable=unused-argument
from collections import deque

import pytest
from async_asgi_testclient import TestClient

from scheduler import queues
from scheduler.app import app


@pytest.mark.asyncio
async def test_queues_initialized():

    async with TestClient(app) as _:
        # discover all queues.AsyncQueue instances defined in the module
        queues_to_test = deque()
        for entry_key in vars(queues):
            module_entry = getattr(queues, entry_key)
            if isinstance(module_entry, queues.AsyncQueue):
                queues_to_test.append(module_entry)

        for k, test_queue in enumerate(queues_to_test):
            test_item = {"index": k}
            print(test_queue)
            assert test_queue is not None
            await test_queue.add(test_item)
            assert test_item == await test_queue.get()
