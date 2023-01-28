import asyncio

import pytest
import tqdm
from servicelib.progress_bar import ProgressBar


async def do_something(root: ProgressBar):
    async with root.sub_progress(steps=50) as sub:
        for n in range(50):
            await sub.update()


async def do_something_else(root: ProgressBar):
    async with root.sub_progress(steps=34) as sub:
        for n in range(17):
            await sub.update(2)


async def test_progress_bar():
    async with ProgressBar(steps=2) as root:
        assert root.progress == 0
        assert root.steps == 2
        await do_something(root)
        assert root.progress == pytest.approx(1)
        assert root.steps == 2
        await do_something_else(root)
        assert root.progress == pytest.approx(2)
        assert root.steps == 2


async def do_something_tqdm():
    with tqdm.tqdm(total=100, desc="1st sub loop") as pbar:
        for n in range(100):
            await asyncio.sleep(0.01)
            pbar.update()


async def do_something_else_tqdm():
    with tqdm.tqdm(total=100, desc="2nd sub loop") as sub:
        for n in range(100):
            await asyncio.sleep(0.01)
            sub.update(2)


async def test_tqdm():
    # for i in tqdm.trange(4, desc="1st loop"):
    #     for j in tqdm.trange(5, desc="2nd loop"):
    #         for k in tqdm.trange(50, desc="3rd loop", leave=False):
    #             sleep(0.01)
    with tqdm.tqdm(total=2, desc="1st loop", position=0) as pbar:
        # await do_something_tqdm()
        with tqdm.tqdm(total=100, desc="1st sub loop", position=1, leave=False) as sub:
            for n in range(100):
                await asyncio.sleep(0.01)
                sub.update()
                pbar.update(1 / 100)
        # await do_something_else_tqdm()
        with tqdm.tqdm(total=100, desc="2nd sub loop", position=1, leave=False) as sub:
            for n in range(100):
                await asyncio.sleep(0.01)
                sub.update()
                pbar.update(1 / 100)
