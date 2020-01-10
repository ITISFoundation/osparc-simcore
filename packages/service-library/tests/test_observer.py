# pylint:disable=wildcard-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from asyncio import Future

from servicelib.observer import emit, observe


async def test_observer(loop, mocker):
    # register a cb function
    cb_function = mocker.Mock(return_value=Future())
    cb_function.return_value.set_result(None)

    decorated_fct = observe(event="my_test_event")(cb_function)

    await emit("my_invalid_test_event")
    cb_function.assert_not_called()
    await emit("my_test_event")
    cb_function.assert_called()
