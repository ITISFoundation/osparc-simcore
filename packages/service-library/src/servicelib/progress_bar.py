import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from servicelib.logging_utils import log_catch

logger = logging.getLogger(__name__)


@runtime_checkable
class AsyncReportCB(Protocol):
    async def __call__(self, progress_value: float) -> None:
        ...


@dataclass
class ProgressBarData:
    """A progress bar data allows to keep track of multiple progress(es) even in deeply nested processes.

    - Simple example:
    async def main_fct():
        async with ProgressBarData(steps=3) as root_progress_bar:
            first_step()
            await root_progress_bar.update()
            second_step()
            await root_progress_bar.update()
            third_step()
            # Note that the last update is not necessary as the context manager ensures the progress bar is complete

    - nested example:

    async def first_step(progress_bar: ProgressBarData):
        async with progress_bar.sub_progress(steps=50) as sub_progress_bar:
            # we create a sub progress bar of 50 steps, that will be stacked into the root progress bar.
            # i.e. when the sub progress bar reaches 50, it will be equivalent of 1 step in the root progress bar.
            for n in range(50):
                await asyncio.sleep(0.01)
                await sub_progress_bar.update()


    async def main_fct():
        async with ProgressBarData(steps=3) as root_progress_bar:
            await first_step(root_progress_bar)
            await second_step()
            await root_progress_bar.update()
            await third_step()
    """

    steps: int = field(
        metadata={"description": "Defines the number of steps in the progress bar"}
    )
    progress_report_cb: Optional[AsyncReportCB] = None
    _continuous_progress_value: float = 0
    _children: list = field(default_factory=list)
    _parent: Optional["ProgressBarData"] = None
    _continuous_value_lock: asyncio.Lock = field(init=False)
    _last_report_value: float = 0

    def __post_init__(self) -> None:
        self._continuous_value_lock = asyncio.Lock()
        self.steps = max(1, self.steps)

    async def __aenter__(self) -> "ProgressBarData":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.finish()

    async def _update_parent(self, value: float) -> None:
        if self._parent:
            await self._parent.update(value / self.steps)

    async def _report_external(self, value: float, force: bool = False) -> None:
        if not self.progress_report_cb:
            return

        with log_catch(logger, reraise=False):
            # NOTE: only report if at least a percent was increased
            if (force and value != self._last_report_value) or (
                ((value - self._last_report_value) / self.steps) > 0.01
            ):
                await self.progress_report_cb(value / self.steps)
                self._last_report_value = value

    async def start(self) -> None:
        await self._report_external(0, force=True)

    async def update(self, value: float = 1) -> None:
        async with self._continuous_value_lock:
            new_progress_value = self._continuous_progress_value + value
            if new_progress_value > self.steps:
                new_progress_value = round(new_progress_value)
            if new_progress_value > self.steps:
                logger.warning(
                    "%s",
                    f"Progress already reached maximum of {self.steps=}, "
                    f"cause: {self._continuous_progress_value=} is updated by {value=}"
                    "TIP: sub progresses are not created correctly please check the stack trace",
                    stack_info=True,
                )

                new_progress_value = self.steps
            self._continuous_progress_value = new_progress_value
        await self._update_parent(value)
        await self._report_external(new_progress_value)

    async def finish(self) -> None:
        await self.update(self.steps - self._continuous_progress_value)
        await self._report_external(self.steps, force=True)

    def sub_progress(self, steps: int) -> "ProgressBarData":
        if len(self._children) == self.steps:
            raise RuntimeError(
                "Too many sub progresses created already. Wrong usage of the progress bar"
            )
        child = ProgressBarData(steps=steps, _parent=self)
        self._children.append(child)
        return child
