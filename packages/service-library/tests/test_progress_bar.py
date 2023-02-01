# pylint: disable=broad-except
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

import asyncio

import pytest
from servicelib.progress_bar import ProgressBarData


async def test_progress_bar():
    async with ProgressBarData(steps=2) as root:
        assert root._continuous_progress == pytest.approx(0)
        assert root.steps == 2
        async with root.sub_progress(steps=50) as sub:
            for _ in range(50):
                await sub.update()
        assert root._continuous_progress == pytest.approx(1)
        assert root.steps == 2
        async with root.sub_progress(steps=50) as sub:
            for _ in range(50):
                await sub.update()
        assert root._continuous_progress == pytest.approx(2)
        assert root.steps == 2


async def test_concurrent_progress_bar():
    async def do_something(root: ProgressBarData):
        async with root.sub_progress(steps=50) as sub:
            assert sub.steps == 50
            assert sub._continuous_progress == 0
            for n in range(50):
                await sub.update()
                assert sub._continuous_progress == (n + 1)

    async with ProgressBarData(steps=12) as root:
        assert root._continuous_progress == pytest.approx(0)
        assert root.steps == 12
        await asyncio.gather(*[do_something(root) for n in range(12)])
        assert root._continuous_progress == pytest.approx(12)


async def test_too_many_sub_progress_bars_raises():
    async with ProgressBarData(steps=2) as root:
        assert root.steps == 2
        async with root.sub_progress(steps=50) as sub:
            for _ in range(50):
                await sub.update()
        async with root.sub_progress(steps=50) as sub:
            for _ in range(50):
                await sub.update()
        with pytest.raises(RuntimeError):
            async with root.sub_progress(steps=50) as sub:
                for _ in range(50):
                    await sub.update()


async def test_too_many_updates_does_not_raise_but_show_warning_with_stack(
    caplog: pytest.LogCaptureFixture,
):
    async with ProgressBarData(steps=2) as root:
        assert root.steps == 2
        await root.update()
        await root.update()
        await root.update()
        assert "already reached maximum" in caplog.messages[0]
        assert "TIP:" in caplog.messages[0]
