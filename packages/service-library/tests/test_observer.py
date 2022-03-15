# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from servicelib.observer import emit, observe


async def test_observer(mocker):
    # register a couroutine as callback function
    cb_function = mocker.AsyncMock(return_value=None)

    decorated_fct = observe(event="my_test_event")(cb_function)

    await emit("my_invalid_test_event")
    cb_function.assert_not_called()
    await emit("my_test_event")
    cb_function.assert_called()
