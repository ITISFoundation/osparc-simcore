# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from datetime import timedelta

from servicelib.decorators import async_delayed, safe_return


def test_safe_return_decorator():
    class AnError(Exception):
        pass

    @safe_return(if_fails_return=False, catch=(AnError,), logger=None)
    def raise_my_exception():
        raise AnError

    assert not raise_my_exception()


def test_safe_return_mutables():
    some_mutable_return = ["some", "defaults"]

    @safe_return(if_fails_return=some_mutable_return)  # type: ignore
    def return_mutable():
        msg = "Runtime is default"
        raise RuntimeError(msg)

    assert return_mutable() == some_mutable_return  # contains the same
    assert return_mutable() is not some_mutable_return  # but is not the same


async def test_async_delayed():
    @async_delayed(timedelta(seconds=0.2))
    async def decorated_awaitable() -> int:
        return 42

    assert await decorated_awaitable() == 42

    async def another_awaitable() -> int:
        return 42

    decorated_another_awaitable = async_delayed(timedelta(seconds=0.2))(
        another_awaitable
    )

    assert await decorated_another_awaitable() == 42
