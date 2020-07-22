# pylint: disable=unused-argument

import asyncio

import pytest
from async_timeout import timeout

from scheduler.queues import AsyncQueue


@pytest.mark.asyncio
async def test_queue_functionality():
    async with AsyncQueue("test") as queue:
        sample_obj = {"some_shit": "me", "hhh": {"hooo": 4, "asd": "me"}}
        await queue.add(sample_obj)
        assert sample_obj == await queue.get()


@pytest.mark.asyncio
async def test_queue_order():
    entries = range(1000)
    async with AsyncQueue("test") as queue:
        # add to queue
        for entry in entries:
            await queue.add(entry)
        # check elements match
        for entry in entries:
            assert entry == await queue.get()


@pytest.mark.asyncio
async def test_queue_get_no_objects():
    async with AsyncQueue("test") as queue:
        with pytest.raises(asyncio.TimeoutError):
            async with timeout(0.1):
                await queue.get()


@pytest.mark.asyncio
async def test_chain_of_queues():
    end_message = None  # stop signal
    entries = [x for x in range(1000)]  # pylint: disable=unnecessary-comprehension

    async def stage_one():
        """Insert all elements in the input queue"""
        async with AsyncQueue("test_input") as input_queue:
            for entry in entries:
                await input_queue.add(entry)
            await input_queue.add(end_message)

    async def stage_two():
        """Fetch all elements from the input queue and put them in the output queue"""
        async with AsyncQueue("test_input") as input_queue, AsyncQueue(
            "test_output"
        ) as output_queue:
            while True:
                entry = await input_queue.get()
                await output_queue.add(entry)
                if entry == end_message:
                    break

    async def stage_three():
        """Validation items from the output queue"""
        found_elements = []
        async with AsyncQueue("test_output") as output_queue:
            while True:
                entry = await output_queue.get()
                if entry == end_message:
                    break
                # validate entry
                found_elements.append(entry)

        assert entries == found_elements

    task_stage_one = asyncio.create_task(stage_one())
    task_stage_two = asyncio.create_task(stage_two())
    task_stage_three = asyncio.create_task(stage_three())

    await task_stage_one
    await task_stage_two
    await task_stage_three
