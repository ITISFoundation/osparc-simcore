import asyncio
import logging
import traceback
from asyncio import Task
from contextlib import suppress
from functools import partial
from typing import Any, Awaitable, Callable, Iterable, Optional

from fastapi import FastAPI
from pydantic import BaseModel, NonNegativeInt

from ._action import Action, PlayCatalog
from ._context_base import ContextInterface, ReservedContextKeys
from ._errors import (
    ActionNotRegisteredException,
    NotInContextError,
    PlayAlreadyRunningException,
    PlayNotFoundException,
)
from ._models import ActionName, PlayName, StepName
from ._play_context import PlayContext

logger = logging.getLogger(__name__)


class ExceptionInfo(BaseModel):
    exception_class: type
    action_name: ActionName
    step_name: StepName
    serialized_traceback: str


def _iter_index_step(
    iterable: Iterable[Callable], *, index: NonNegativeInt = 0
) -> Iterable[tuple[NonNegativeInt, Callable]]:
    for i, value in enumerate(iterable):
        if i >= index:
            yield i, value


async def action_player(
    play_catalog: PlayCatalog,
    play_context: PlayContext,
    *,
    before_step_hook: Optional[
        Callable[[ActionName, StepName], Awaitable[None]]
    ] = None,
    after_step_hook: Optional[Callable[[ActionName, StepName], Awaitable[None]]] = None,
) -> None:
    """
    Given a `PlayCatalog` and a `PlayContext` runs from a given
    starting action.
    Can also recover from an already initialized `PlayContext`.
    """

    # goes through all the states defined and does tuff right?
    # not in some cases this needs to end, these are ran as tasks
    #
    action_name: ActionName = await play_context.get(
        ReservedContextKeys.PLAY_ACTION_NAME, ActionName
    )
    action: Optional[Action] = play_catalog[action_name]

    start_from_index: int = 0
    try:
        start_from_index = await play_context.get(
            ReservedContextKeys.PLAY_CURRENT_STEP_INDEX, int
        )
    except NotInContextError:
        pass

    while action is not None:
        action_name = action.name
        await play_context.set(
            ReservedContextKeys.PLAY_ACTION_NAME, action_name, set_reserved=True
        )
        logger.debug("Running action='%s', step=%s", action_name, action.steps_names)
        try:
            for index, step in _iter_index_step(action.steps, index=start_from_index):
                step_name = step.__name__

                if before_step_hook:
                    await before_step_hook(action_name, step_name)

                # fetching inputs from context
                inputs: dict[str, Any] = {}
                if step.input_types:
                    get_inputs_results = await asyncio.gather(
                        *[
                            play_context.get(var_name, var_type)
                            for var_name, var_type in step.input_types.items()
                        ]
                    )
                    inputs = dict(zip(step.input_types, get_inputs_results))
                logger.debug("step='%s' inputs=%s", step_name, inputs)

                # running event handler
                await play_context.set(
                    ReservedContextKeys.PLAY_CURRENT_STEP_NAME,
                    step_name,
                    set_reserved=True,
                )
                await play_context.set(
                    ReservedContextKeys.PLAY_CURRENT_STEP_INDEX,
                    index,
                    set_reserved=True,
                )
                result = await step(**inputs)

                # saving outputs to context
                logger.debug("step='%s' result=%s", step_name, result)
                await asyncio.gather(
                    *[
                        play_context.set(key=var_name, value=var_value)
                        for var_name, var_value in result.items()
                    ]
                )

                if after_step_hook:
                    await after_step_hook(action_name, step_name)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected exception, deferring handling to action='%s'",
                action.on_error_action,
            )

            if action.on_error_action is None:
                # NOTE: since there is no state that takes care of the error
                # just raise it here and halt the task
                logger.error("play_context=%s", await play_context.to_dict())
                raise

            # Storing exception to be possibly handled by the error state
            exception_info = ExceptionInfo(
                exception_class=e.__class__,
                action_name=await play_context.get(
                    ReservedContextKeys.PLAY_ACTION_NAME, PlayName
                ),
                step_name=await play_context.get(
                    ReservedContextKeys.PLAY_CURRENT_STEP_NAME, ActionName
                ),
                serialized_traceback=traceback.format_exc(),
            )
            await play_context.set(
                ReservedContextKeys.EXCEPTION, exception_info, set_reserved=True
            )

            action = (
                None
                if action.on_error_action is None
                else play_catalog[action.on_error_action]
            )
        else:
            action = (
                None if action.next_action is None else play_catalog[action.next_action]
            )
        finally:
            start_from_index = 0


class PlayerManager:
    """
    Keeps track of running `action_player`s and is responsible for:
    starting, stopping and cancelling them.
    """

    def __init__(
        self,
        context: ContextInterface,
        app: FastAPI,
        play_catalog: PlayCatalog,
        *,
        before_step_hook: Optional[
            Callable[[ActionName, StepName], Awaitable[None]]
        ] = None,
        after_step_hook: Optional[
            Callable[[ActionName, StepName], Awaitable[None]]
        ] = None,
    ) -> None:
        self.context = context
        self.app = app
        self.play_catalog = play_catalog
        self.before_step_hook = before_step_hook
        self.after_step_hook = after_step_hook

        self._player_tasks: dict[PlayName, Task] = {}
        self._play_context: dict[PlayName, PlayContext] = {}
        self._shutdown_tasks_play_context: dict[PlayName, Task] = {}

    async def start_action_player(
        self, play_name: PlayName, action_name: ActionName
    ) -> None:
        """starts a new workflow with a unique name"""

        if play_name in self._play_context:
            raise PlayAlreadyRunningException(play_name=play_name)
        if action_name not in self.play_catalog:
            raise ActionNotRegisteredException(
                action_name=action_name, play_catalog=self.play_catalog
            )

        self._play_context[play_name] = play_context = PlayContext(
            context=self.context,
            app=self.app,
            play_name=play_name,
            action_name=action_name,
        )
        await play_context.setup()

        action_player_awaitable: Awaitable = action_player(
            play_catalog=self.play_catalog,
            play_context=play_context,
            before_step_hook=self.before_step_hook,
            after_step_hook=self.after_step_hook,
        )

        self._create_action_player_task(action_player_awaitable, play_name)

    async def resume_action_player(self, play_context: PlayContext) -> None:
        # NOTE: expecting `await play_context.start()` to have already been ran

        action_player_awaitable: Awaitable = action_player(
            play_catalog=self.play_catalog,
            play_context=play_context,
            before_step_hook=self.before_step_hook,
            after_step_hook=self.after_step_hook,
        )

        play_name: PlayName = await play_context.get(
            ReservedContextKeys.PLAY_NAME, PlayName
        )
        self._create_action_player_task(action_player_awaitable, play_name)

    def _create_action_player_task(
        self, action_player_awaitable: Awaitable, play_name: PlayName
    ) -> None:
        play_task = self._player_tasks[play_name] = asyncio.create_task(
            action_player_awaitable, name=play_name
        )

        def action_player_complete(_: Task) -> None:
            self._player_tasks.pop(play_name, None)
            play_context: Optional[PlayContext] = self._play_context.pop(
                play_name, None
            )
            if play_context:
                # shutting down context resolver and ensure task will not be pending
                task = self._shutdown_tasks_play_context[
                    play_name
                ] = asyncio.create_task(play_context.teardown())
                task.add_done_callback(
                    partial(
                        lambda s, _: self._shutdown_tasks_play_context.pop(s, None),
                        play_name,
                    )
                )

        # remove when task is done
        play_task.add_done_callback(action_player_complete)

    async def wait_action_player(self, play_name: PlayName) -> None:
        """waits for action play task to finish"""
        if play_name not in self._player_tasks:
            raise PlayNotFoundException(workflow_name=play_name)

        player_task = self._player_tasks[play_name]
        await player_task

    @staticmethod
    async def __cancel_task(task: Optional[Task]) -> None:
        if task is None:
            return

        async def _await_task(task: Task) -> None:
            await task

        task.cancel()
        with suppress(asyncio.CancelledError):
            try:
                await asyncio.wait_for(_await_task(task), timeout=10)
            except asyncio.TimeoutError:
                logger.warning(
                    "Timed out while awaiting for cancellation of '%s'", task.get_name()
                )

    async def cancel_action_player(self, play_name: PlayName) -> None:
        """cancels current action player Task"""
        if play_name not in self._player_tasks:
            raise PlayNotFoundException(workflow_name=play_name)

        task = self._player_tasks[play_name]
        await self.__cancel_task(task)

    async def teardown(self) -> None:
        # NOTE: content can change while iterating
        for key in set(self._play_context.keys()):
            play_context: Optional[PlayContext] = self._play_context.get(key, None)
            if play_context:
                await play_context.teardown()

        # NOTE: content can change while iterating
        for key in set(self._shutdown_tasks_play_context.keys()):
            task: Optional[Task] = self._shutdown_tasks_play_context.get(key, None)
            await self.__cancel_task(task)

    async def setup(self) -> None:
        """currently not required"""
