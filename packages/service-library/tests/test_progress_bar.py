# pylint: disable=broad-except
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

import asyncio

import pytest
from servicelib.progress_bar import ProgressData


async def test_progress_bar():
    async with ProgressData(steps=2) as root:
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
    async def do_something(root: ProgressData):
        async with root.sub_progress(steps=50) as sub:
            assert sub.steps == 50
            assert sub._continuous_progress == 0
            for n in range(50):
                await sub.update()
                assert sub._continuous_progress == (n + 1)

    async with ProgressData(steps=12) as root:
        assert root._continuous_progress == pytest.approx(0)
        assert root.steps == 12
        await asyncio.gather(*[do_something(root) for n in range(12)])
        assert root._continuous_progress == pytest.approx(12)


async def test_too_many_sub_progress_bars_raises():
    async with ProgressData(steps=2) as root:
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


async def test_too_many_updates_raises():
    async with ProgressData(steps=2) as root:
        assert root.steps == 2
        await root.update()
        await root.update()
        with pytest.raises(ValueError):
            await root.update()
