# pylint: disable=broad-except
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

import asyncio
from unittest import mock

import pytest
from pytest_mock import MockerFixture
from servicelib.progress_bar import _FINAL_VALUE, _INITIAL_VALUE, ProgressBarData


@pytest.fixture
def mocked_progress_bar_cb(mocker: MockerFixture) -> mock.Mock:
    return mocker.Mock()


@pytest.fixture
def async_mocked_progress_bar_cb(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.AsyncMock()


@pytest.mark.parametrize(
    "progress_report_cb_type",
    ["mocked_progress_bar_cb", "async_mocked_progress_bar_cb"],
)
async def test_progress_bar(
    progress_report_cb_type: str,
    mocked_progress_bar_cb: mock.Mock,
    async_mocked_progress_bar_cb: mock.AsyncMock,
):
    mocked_cb = {
        "mocked_progress_bar_cb": mocked_progress_bar_cb,
        "async_mocked_progress_bar_cb": async_mocked_progress_bar_cb,
    }[progress_report_cb_type]

    async with ProgressBarData(num_steps=3, progress_report_cb=mocked_cb) as root:
        assert root.num_steps == 3
        assert root.step_weights is None  # i.e. all steps have equal weight
        assert root._current_steps == pytest.approx(0)  # noqa: SLF001
        mocked_cb.assert_called_once_with(pytest.approx(0))
        mocked_cb.reset_mock()
        # first step is done right away
        await root.update()
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001
        mocked_cb.assert_called_once_with(pytest.approx(1 / 3))
        mocked_cb.reset_mock()

        # 2nd step is a sub progress bar of 10 steps
        async with root.sub_progress(steps=10) as sub:
            assert sub._current_steps == pytest.approx(0)  # noqa: SLF001
            assert root._current_steps == pytest.approx(1)  # noqa: SLF001
            for i in range(10):
                await sub.update()
                assert sub._current_steps == pytest.approx(float(i + 1))  # noqa: SLF001
                assert root._current_steps == pytest.approx(  # noqa: SLF001
                    1 + float(i + 1) / 10.0
                )
        assert root._current_steps == pytest.approx(2)  # noqa: SLF001
        mocked_cb.assert_called()
        assert mocked_cb.call_count == 10
        assert mocked_cb.call_args_list[9].args[0] == pytest.approx(2 / 3)
        mocked_cb.reset_mock()

        # 3rd step is another subprogress of 50 steps
        async with root.sub_progress(steps=50) as sub:
            assert sub._current_steps == pytest.approx(0)  # noqa: SLF001
            assert root._current_steps == pytest.approx(2)  # noqa: SLF001
            for i in range(50):
                await sub.update()
                assert sub._current_steps == pytest.approx(float(i + 1))  # noqa: SLF001
                assert root._current_steps == pytest.approx(  # noqa: SLF001
                    2 + float(i + 1) / 50.0
                )
        assert root._current_steps == pytest.approx(3)  # noqa: SLF001
        mocked_cb.assert_called()
        assert mocked_cb.call_count == 25
        assert mocked_cb.call_args_list[24].args[0] == pytest.approx(1)
        mocked_cb.reset_mock()


async def test_progress_bar_always_reports_0_on_creation_and_1_on_finish(
    mocked_progress_bar_cb: mock.Mock,
):
    num_steps = 156587
    progress_bar = ProgressBarData(
        num_steps=num_steps, progress_report_cb=mocked_progress_bar_cb
    )
    assert progress_bar._current_steps == _INITIAL_VALUE  # noqa: SLF001
    async with progress_bar as root:
        assert root is progress_bar
        assert root._current_steps == 0  # noqa: SLF001
        mocked_progress_bar_cb.assert_called_once_with(0)

    # going out of scope always updates to final number of steps
    assert progress_bar._current_steps == num_steps  # noqa: SLF001
    assert mocked_progress_bar_cb.call_args_list[-1] == mock.call(_FINAL_VALUE)


async def test_progress_bar_always_reports_1_on_finish(
    mocked_progress_bar_cb: mock.Mock,
):
    num_steps = 156587
    chunks = 123.3

    num_chunked_steps = int(num_steps / chunks)
    last_step = num_steps % chunks
    progress_bar = ProgressBarData(
        num_steps=num_steps, progress_report_cb=mocked_progress_bar_cb
    )
    assert progress_bar._current_steps == _INITIAL_VALUE  # noqa: SLF001
    async with progress_bar as root:
        assert root is progress_bar
        assert root._current_steps == 0  # noqa: SLF001
        mocked_progress_bar_cb.assert_called_once_with(0)
        for _ in range(num_chunked_steps):
            await root.update(chunks)
        await root.update(last_step)
        assert progress_bar._current_steps == pytest.approx(num_steps)  # noqa: SLF001

    # going out of scope always updates to final number of steps
    assert progress_bar._current_steps == pytest.approx(num_steps)  # noqa: SLF001
    assert mocked_progress_bar_cb.call_args_list[-1] == mock.call(_FINAL_VALUE)


async def test_set_progress(
    caplog: pytest.LogCaptureFixture,
):
    async with ProgressBarData(num_steps=50) as root:
        assert root._current_steps == pytest.approx(0)  # noqa: SLF001
        assert root.num_steps == 50
        assert root.step_weights is None
        await root.set_(13)
        assert root._current_steps == pytest.approx(13)  # noqa: SLF001
        await root.set_(34)
        assert root._current_steps == pytest.approx(34)  # noqa: SLF001
        await root.set_(58)
        assert root._current_steps == pytest.approx(50)  # noqa: SLF001
        assert "already reached maximum" in caplog.messages[0]
        assert "TIP:" in caplog.messages[0]


async def test_concurrent_progress_bar():
    async def do_something(root: ProgressBarData):
        async with root.sub_progress(steps=50) as sub:
            assert sub.num_steps == 50
            assert sub.step_weights is None
            assert sub._current_steps == 0  # noqa: SLF001
            for n in range(50):
                await sub.update()
                assert sub._current_steps == (n + 1)  # noqa: SLF001

    async with ProgressBarData(num_steps=12) as root:
        assert root._current_steps == pytest.approx(0)  # noqa: SLF001
        assert root.step_weights is None
        await asyncio.gather(*[do_something(root) for n in range(12)])
        assert root._current_steps == pytest.approx(12)  # noqa: SLF001


async def test_too_many_sub_progress_bars_raises():
    async with ProgressBarData(num_steps=2) as root:
        assert root.num_steps == 2
        assert root.step_weights is None
        async with root.sub_progress(steps=50) as sub:
            for _ in range(50):
                await sub.update()
        async with root.sub_progress(steps=50) as sub:
            for _ in range(50):
                await sub.update()

        with pytest.raises(RuntimeError):
            async with root.sub_progress(steps=50) as sub:
                ...


async def test_too_many_updates_does_not_raise_but_show_warning_with_stack(
    caplog: pytest.LogCaptureFixture,
):
    async with ProgressBarData(num_steps=2) as root:
        assert root.num_steps == 2
        assert root.step_weights is None
        await root.update()
        await root.update()
        await root.update()
        assert "already reached maximum" in caplog.messages[0]
        assert "TIP:" in caplog.messages[0]


async def test_weighted_progress_bar(mocked_progress_bar_cb: mock.Mock):
    async with ProgressBarData(
        num_steps=3,
        step_weights=[1, 3, 1],
        progress_report_cb=mocked_progress_bar_cb,
    ) as root:
        mocked_progress_bar_cb.assert_called_once_with(pytest.approx(0))
        mocked_progress_bar_cb.reset_mock()
        assert root.step_weights == [1 / 5, 3 / 5, 1 / 5, 0]
        await root.update()
        mocked_progress_bar_cb.assert_called_once_with(pytest.approx(1 / 5))
        mocked_progress_bar_cb.reset_mock()
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001
        await root.update()
        mocked_progress_bar_cb.assert_called_once_with(pytest.approx(1 / 5 + 3 / 5))
        mocked_progress_bar_cb.reset_mock()
        assert root._current_steps == pytest.approx(2)  # noqa: SLF001
    mocked_progress_bar_cb.assert_called_once_with(1)
    mocked_progress_bar_cb.reset_mock()
    assert root._current_steps == pytest.approx(3)  # noqa: SLF001


async def test_weighted_progress_bar_with_weighted_sub_progress(
    mocked_progress_bar_cb: mock.Mock,
):
    async with ProgressBarData(
        num_steps=3,
        step_weights=[1, 3, 1],
        progress_report_cb=mocked_progress_bar_cb,
    ) as root:
        mocked_progress_bar_cb.assert_called_once_with(pytest.approx(0))
        mocked_progress_bar_cb.reset_mock()
        assert root.step_weights == [1 / 5, 3 / 5, 1 / 5, 0]
        # first step
        await root.update()
        mocked_progress_bar_cb.assert_called_once_with(pytest.approx(1 / 5))
        mocked_progress_bar_cb.reset_mock()
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001

        # 2nd step is a sub progress bar of 5 steps
        async with root.sub_progress(steps=5, step_weights=[2, 5, 1, 2, 3]) as sub:
            assert sub.step_weights == [2 / 13, 5 / 13, 1 / 13, 2 / 13, 3 / 13, 0]
            assert sub._current_steps == pytest.approx(0)  # noqa: SLF001
            assert root._current_steps == pytest.approx(1)  # noqa: SLF001
            # sub steps
            # 1
            await sub.update()
            assert sub._current_steps == pytest.approx(1)  # noqa: SLF001
            assert root._current_steps == pytest.approx(1 + 2 / 13)  # noqa: SLF001
            # 2
            await sub.update()
            assert sub._current_steps == pytest.approx(2)  # noqa: SLF001
            assert root._current_steps == pytest.approx(  # noqa: SLF001
                1 + 2 / 13 + 5 / 13
            )
            # 3
            await sub.update()
            assert sub._current_steps == pytest.approx(3)  # noqa: SLF001
            assert root._current_steps == pytest.approx(  # noqa: SLF001
                1 + 2 / 13 + 5 / 13 + 1 / 13
            )
            # 4
            await sub.update()
            assert sub._current_steps == pytest.approx(4)  # noqa: SLF001
            assert root._current_steps == pytest.approx(  # noqa: SLF001
                1 + 2 / 13 + 5 / 13 + 1 / 13 + 2 / 13
            )
            # 5
            await sub.update()
            assert sub._current_steps == pytest.approx(5)  # noqa: SLF001
            assert root._current_steps == pytest.approx(2)  # noqa: SLF001

        assert root._current_steps == pytest.approx(2)  # noqa: SLF001
        mocked_progress_bar_cb.assert_called()
        assert mocked_progress_bar_cb.call_count == 5
        assert mocked_progress_bar_cb.call_args_list[4].args[0] == pytest.approx(
            1 / 5 + 3 / 5
        )
        mocked_progress_bar_cb.reset_mock()
        assert root._current_steps == pytest.approx(2)  # noqa: SLF001
    mocked_progress_bar_cb.assert_called_once_with(1)
    mocked_progress_bar_cb.reset_mock()
    assert root._current_steps == pytest.approx(3)  # noqa: SLF001


async def test_weighted_progress_bar_wrong_num_weights_raises():
    with pytest.raises(RuntimeError):
        async with ProgressBarData(
            num_steps=3,
            step_weights=[3, 1],
        ):
            ...


async def test_weighted_progress_bar_with_0_weights_is_equivalent_to_standard_progress_bar():
    async with ProgressBarData(
        num_steps=3,
        step_weights=[0, 0, 0],
    ) as root:
        assert root.step_weights == [1, 1, 1, 0]
