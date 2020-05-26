from asyncio import Future


def future_with_result(result) -> Future:
    f = Future()
    f.set_result(result)
    return f
