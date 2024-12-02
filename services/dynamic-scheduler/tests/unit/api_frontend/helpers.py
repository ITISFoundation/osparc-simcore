# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final
from uuid import uuid4

from playwright.async_api import Locator, Page
from pydantic import NonNegativeFloat, NonNegativeInt
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed

_HERE: Final[Path] = (
    Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
)
_DEFAULT_TIMEOUT: Final[NonNegativeFloat] = 10


@asynccontextmanager
async def _take_screenshot_on_error(
    async_page: Page,
) -> AsyncIterator[None]:
    try:
        yield
    # allows to also capture exceptions form `with pytest.raise(...)``
    except BaseException:
        path = _HERE / f"{uuid4()}.ignore.png"
        await async_page.screenshot(path=path)
        print(f"Please check :{path}")

        raise


async def _get_locator(
    async_page: Page,
    text: str,
    instances: NonNegativeInt | None,
    timeout: float,  # noqa: ASYNC109
) -> Locator:
    async with _take_screenshot_on_error(async_page):
        async for attempt in AsyncRetrying(
            reraise=True, wait=wait_fixed(0.1), stop=stop_after_delay(timeout)
        ):
            with attempt:
                locator = async_page.get_by_text(text)
                count = await locator.count()
                if instances is None:
                    assert count > 0, f"cold not find text='{text}'"
                else:
                    assert (
                        count == instances
                    ), f"found {count} instances of text='{text}'. Expected {instances}"
    return locator


async def assert_contains_text(
    async_page: Page,
    text: str,
    instances: NonNegativeInt | None = None,
    timeout: float = _DEFAULT_TIMEOUT,  # noqa: ASYNC109
) -> None:
    await _get_locator(async_page, text, instances=instances, timeout=timeout)


async def click_on_text(
    async_page: Page,
    text: str,
    instances: NonNegativeInt | None = None,
    timeout: float = _DEFAULT_TIMEOUT,  # noqa: ASYNC109
) -> None:
    locator = await _get_locator(async_page, text, instances=instances, timeout=timeout)
    await locator.click()


async def assert_not_contains_text(
    async_page: Page,
    text: str,
    timeout: float = _DEFAULT_TIMEOUT,  # noqa: ASYNC109
) -> None:
    async with _take_screenshot_on_error(async_page):
        async for attempt in AsyncRetrying(
            reraise=True, wait=wait_fixed(0.1), stop=stop_after_delay(timeout)
        ):
            with attempt:
                locator = async_page.get_by_text(text)
                assert await locator.count() < 1, f"found text='{text}' in body"
