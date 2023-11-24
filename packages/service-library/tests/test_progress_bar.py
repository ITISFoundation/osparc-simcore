# pylint: disable=broad-except
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

import asyncio
from unittest import mock

import pytest
from pytest_mock import MockerFixture
from servicelib.progress_bar import ProgressBarData


@pytest.fixture
def mocked_progress_bar_cb(mocker: MockerFixture) -> mock.Mock:
    return mocker.Mock()


async def test_progress_bar(mocked_progress_bar_cb: mock.Mock):
    async with ProgressBarData(
        steps=2, progress_report_cb=mocked_progress_bar_cb
    ) as root:
        assert root._continuous_progress_value == pytest.approx(0)  # noqa: SLF001
        mocked_progress_bar_cb.assert_called_once_with(pytest.approx(0))
        mocked_progress_bar_cb.reset_mock()
        assert root.steps == 2
        assert root.step_weights is None
        async with root.sub_progress(steps=50) as sub:
            for _ in range(50):
                await sub.update()
        assert root._continuous_progress_value == pytest.approx(1)  # noqa: SLF001
        mocked_progress_bar_cb.assert_called()
        assert mocked_progress_bar_cb.call_count == 43
        assert mocked_progress_bar_cb.call_args_list[43] == 2
        mocked_progress_bar_cb.reset_mock()
        assert root.steps == 2
        async with root.sub_progress(steps=50) as sub:
            for _ in range(50):
                await sub.update()
        assert root._continuous_progress_value == pytest.approx(2)  # noqa: SLF001
        mocked_progress_bar_cb.assert_called()
        assert mocked_progress_bar_cb.call_count == 49
        assert mocked_progress_bar_cb.call_args_list[49] == 2
        mocked_progress_bar_cb.reset_mock()
        assert root.steps == 2


async def test_set_progress(
    caplog: pytest.LogCaptureFixture,
):
    async with ProgressBarData(steps=50) as root:
        assert root._continuous_progress_value == pytest.approx(0)  # noqa: SLF001
        assert root.steps == 50
        assert root.step_weights is None
        await root.set_progress(13)
        assert root._continuous_progress_value == pytest.approx(13)  # noqa: SLF001
        await root.set_progress(34)
        assert root._continuous_progress_value == pytest.approx(34)  # noqa: SLF001
        await root.set_progress(58)
        assert root._continuous_progress_value == pytest.approx(50)  # noqa: SLF001
        assert "already reached maximum" in caplog.messages[0]
        assert "TIP:" in caplog.messages[0]


async def test_concurrent_progress_bar():
    async def do_something(root: ProgressBarData):
        async with root.sub_progress(steps=50) as sub:
            assert sub.steps == 50
            assert sub.step_weights is None
            assert sub._continuous_progress_value == 0  # noqa: SLF001
            for n in range(50):
                await sub.update()
                assert sub._continuous_progress_value == (n + 1)  # noqa: SLF001

    async with ProgressBarData(steps=12) as root:
        assert root._continuous_progress_value == pytest.approx(0)  # noqa: SLF001
        assert root.step_weights is None
        await asyncio.gather(*[do_something(root) for n in range(12)])
        assert root._continuous_progress_value == pytest.approx(12)  # noqa: SLF001


async def test_too_many_sub_progress_bars_raises():
    async with ProgressBarData(steps=2) as root:
        assert root.steps == 2
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
    async with ProgressBarData(steps=2) as root:
        assert root.steps == 2
        assert root.step_weights is None
        await root.update()
        await root.update()
        await root.update()
        assert "already reached maximum" in caplog.messages[0]
        assert "TIP:" in caplog.messages[0]


async def test_weighted_progress_bar(mocked_progress_bar_cb: mock.Mock):
    async with ProgressBarData(
        steps=3,
        step_weights=[1, 3, 1],
        progress_report_cb=mocked_progress_bar_cb,
    ) as root:
        mocked_progress_bar_cb.assert_called_once_with(pytest.approx(0))
        mocked_progress_bar_cb.reset_mock()
        assert root.step_weights == [1 / 5, 3 / 5, 1 / 5, 0]
        await root.update()
        mocked_progress_bar_cb.assert_called_once_with(pytest.approx(1 / 5 * 3))
        mocked_progress_bar_cb.reset_mock()
        assert root._continuous_progress_value == pytest.approx(1)  # noqa: SLF001
        await root.update()
        mocked_progress_bar_cb.assert_called_once_with(
            pytest.approx(1 / 5 * 3 + 3 / 5 * 3)
        )
        mocked_progress_bar_cb.reset_mock()
        assert root._continuous_progress_value == pytest.approx(2)  # noqa: SLF001
    mocked_progress_bar_cb.assert_called_once_with(3)
    mocked_progress_bar_cb.reset_mock()
    assert root._continuous_progress_value == pytest.approx(3)  # noqa: SLF001
