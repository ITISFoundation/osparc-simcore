import asyncio


async def some_long_running_task():
    try:
        print("some_long_running_task started")
        await asyncio.sleep(10)
        print("some_long_running_task completed")  # Doesn't execute if cancelled
    except asyncio.CancelledError:
        print("some_long_running_task was cancelled, cleaning up")  # Executes
        await asyncio.sleep(3)  # Simulate cleanup
        print("some_long_running_task was cancelled, cleanup done")  # Executes
        raise


async def parent_task():
    task = asyncio.create_task(some_long_running_task())
    #
    # ✅ Synchronous code continues executing normally!
    x = 1 + 1  # Executes
    print("sleep 2sec")  # Executes
    await asyncio.sleep(2)  # Executes
    current_task = asyncio.current_task()
    assert current_task  # nosec
    current_task.cancel()  # Cancels parent_task
    print(
        f"we are cancelled now, calling cancel_wait_task {current_task.cancelling()}"
    )  # Executes

    await cancel_wait_task(task)


async def cancel_wait_task(task, *, max_delay=None):
    # ✅ All synchronous code executes normally
    current_task = asyncio.current_task()
    assert current_task is not None  # nosec
    try:
        print(f"doing stuff before task cancel: {current_task.cancelling()}")
        task.cancel()
        print("sleeping a bit  after task cancel")
        # current_task.uncancel()
        # try:
        #     await asyncio.sleep(1)
        # except asyncio.CancelledError:
        #     ...
        # await asyncio.sleep(1)
        print("done sleeping a bit  now wait for task to complete")
        await task
        # await asyncio.shield(await asyncio.wait_for(task, timeout=max_delay))
        print("doing stuff after wait_for")
        await asyncio.sleep(1)
        print("done with sleeping after wait_for")
    except asyncio.CancelledError:
        print("task was cancelled inside cancel_wait_task")

        print(
            f"current task {current_task.get_name()} with {current_task.cancelling()}"
        )
        if current_task.cancelling() > 0:
            print(
                "propagating cancellation from parent_task as we seem to be cancelled"
            )  # Executes
            raise


if __name__ == "__main__":
    try:
        asyncio.run(parent_task())
    except asyncio.CancelledError:
        print("parent_task was cancelled")  # Executes
