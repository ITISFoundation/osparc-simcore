import asyncio
import logging
from dataclasses import dataclass, field
from inspect import isawaitable
from typing import Final, Optional, Protocol, runtime_checkable

from .logging_utils import log_catch

logger = logging.getLogger(__name__)
_MIN_PROGRESS_UPDATE_PERCENT: Final[float] = 0.01
_FINAL_VALUE: Final[float] = 1.0


@runtime_checkable
class AsyncReportCB(Protocol):
    async def __call__(self, progress_value: float) -> None:
        ...


@runtime_checkable
class ReportCB(Protocol):
    def __call__(self, progress_value: float) -> None:
        ...


def _normalize_weights(steps: int, weights: list[float]) -> list[float]:
    total = sum(weights)
    if total == 0:
        return [1] * steps
    return [weight / total for weight in weights]


_INITIAL_VALUE: Final[float] = -1


@dataclass(slots=True, kw_only=True)
class ProgressBarData:
    """A progress bar data allows to keep track of multiple progress(es) even in deeply nested processes.

    - Simple example:
    async def main_fct():
        async with ProgressBarData(num_steps=3) as root_progress_bar:
            first_step()
            await root_progress_bar.update()
            second_step()
            await root_progress_bar.update()
            third_step()
            # Note that the last update is not necessary as the context manager ensures the progress bar is complete

    - nested example:

    async def first_step(progress_bar: ProgressBarData):
        async with progress_bar.sub_progress(num_steps=50) as sub_progress_bar:
            # we create a sub progress bar of 50 steps, that will be stacked into the root progress bar.
            # i.e. when the sub progress bar reaches 50, it will be equivalent of 1 step in the root progress bar.
            for n in range(50):
                await asyncio.sleep(0.01)
                await sub_progress_bar.update()


    async def main_fct():
        async with ProgressBarData(num_steps=3) as root_progress_bar:
            await first_step(root_progress_bar)
            await second_step()
            await root_progress_bar.update()
            await third_step()
    """

    num_steps: int = field(
        metadata={"description": "Defines the number of steps in the progress bar"}
    )
    step_weights: list[float] | None = field(
        default=None,
        metadata={
            "description": "Optionally defines the step relative weight (defaults to steps of equal weights)"
        },
    )
    progress_report_cb: AsyncReportCB | ReportCB | None = None
    _current_steps: float = _INITIAL_VALUE
    _children: list = field(default_factory=list)
    _parent: Optional["ProgressBarData"] = None
    _continuous_value_lock: asyncio.Lock = field(init=False)
    _last_report_value: float = _INITIAL_VALUE

    def __post_init__(self) -> None:
        self._continuous_value_lock = asyncio.Lock()
        self.num_steps = max(1, self.num_steps)
        if self.step_weights:
            if len(self.step_weights) != self.num_steps:
                msg = f"{self.num_steps=} and {len(self.step_weights)} weights provided! Wrong usage of ProgressBarData"
                raise RuntimeError(msg)
            self.step_weights = _normalize_weights(self.num_steps, self.step_weights)
            self.step_weights.append(0)  # NOTE: needed to compute reports

    async def __aenter__(self) -> "ProgressBarData":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.finish()

    async def _update_parent(self, value: float) -> None:
        if self._parent:
            await self._parent.update(value)

    async def _report_external(self, value: float, *, force: bool = False) -> None:
        if not self.progress_report_cb:
            return

        with log_catch(logger, reraise=False):
            # NOTE: only report if at least a percent was increased
            if (
                (force and value != self._last_report_value)
                or ((value - self._last_report_value) > _MIN_PROGRESS_UPDATE_PERCENT)
                or value == _FINAL_VALUE
            ):
                call = self.progress_report_cb(value)
                if isawaitable(call):
                    await call
                self._last_report_value = value

    async def start(self) -> None:
        await self.set_(0)

    def _compute_progress(self, steps: float) -> float:
        if not self.step_weights:
            return steps / self.num_steps
        weight_index = int(steps)
        return (
            sum(self.step_weights[:weight_index])
            + steps % 1 * self.step_weights[weight_index]
        )

    async def update(self, steps: float = 1) -> None:
        parent_update_value = 0.0
        async with self._continuous_value_lock:
            new_steps_value = self._current_steps + steps
            if new_steps_value > self.num_steps:
                new_steps_value = round(new_steps_value)
            if new_steps_value > self.num_steps:
                logger.warning(
                    "%s",
                    f"Progress already reached maximum of {self.num_steps=}, "
                    f"cause: {self._current_steps=} is updated by {steps=}"
                    "TIP: sub progresses are not created correctly please check the stack trace",
                    stack_info=True,
                )

                new_steps_value = self.num_steps

            new_progress_value = self._compute_progress(new_steps_value)
            if self._current_steps != _INITIAL_VALUE:
                old_progress_value = self._compute_progress(self._current_steps)
                parent_update_value = new_progress_value - old_progress_value
            self._current_steps = new_steps_value

        if parent_update_value:
            await self._update_parent(parent_update_value)
        await self._report_external(new_progress_value)

    async def set_(self, new_value: float) -> None:
        if update_value := round(new_value - self._current_steps):
            await self.update(update_value)

    async def finish(self) -> None:
        await self.set_(self.num_steps)

    def sub_progress(
        self, steps: int, step_weights: list[float] | None = None
    ) -> "ProgressBarData":
        if len(self._children) == self.num_steps:
            msg = "Too many sub progresses created already. Wrong usage of the progress bar"
            raise RuntimeError(msg)
        child = ProgressBarData(
            num_steps=steps, step_weights=step_weights, _parent=self
        )
        self._children.append(child)
        return child
