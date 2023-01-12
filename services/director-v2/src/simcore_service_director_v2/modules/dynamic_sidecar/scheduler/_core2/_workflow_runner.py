import logging
import traceback
from typing import Any, Awaitable, Callable, Iterable, Optional

from pydantic import NonNegativeInt
from servicelib.utils import logged_gather

from ._action import Action
from ._context_base import ReservedContextKeys
from ._errors import NotInContextError
from ._models import ActionName, ExceptionInfo, StepName, WorkflowName
from ._workflow import Workflow
from ._workflow_context import WorkflowContext

logger = logging.getLogger(__name__)


def _iter_index_step(
    iterable: Iterable[Callable], *, index: NonNegativeInt = 0
) -> Iterable[tuple[NonNegativeInt, Callable]]:
    for i, value in enumerate(iterable):
        if i >= index:
            yield i, value


async def workflow_runner(
    workflow: Workflow,
    workflow_context: WorkflowContext,
    *,
    before_step_hook: Optional[
        Callable[[ActionName, StepName], Awaitable[None]]
    ] = None,
    after_step_hook: Optional[Callable[[ActionName, StepName], Awaitable[None]]] = None,
) -> None:
    """
    Given a `Workflow` and a `WorkflowContext`:
    - runs from a given starting action
    - recovers from an already initialized `WorkflowContext`
    """

    action_name: ActionName = await workflow_context.get(
        ReservedContextKeys.WORKFLOW_ACTION_NAME, ActionName
    )
    action: Optional[Action] = workflow[action_name]

    start_from_index: int = 0
    try:
        start_from_index = await workflow_context.get(
            ReservedContextKeys.WORKFLOW_CURRENT_STEP_INDEX, int
        )
    except NotInContextError:
        pass

    while action is not None:
        action_name = action.name
        await workflow_context.set(
            ReservedContextKeys.WORKFLOW_ACTION_NAME, action_name, set_reserved=True
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
                    get_inputs_results = await logged_gather(
                        *[
                            workflow_context.get(var_name, var_type)
                            for var_name, var_type in step.input_types.items()
                        ]
                    )
                    inputs = dict(zip(step.input_types, get_inputs_results))
                logger.debug("step='%s' inputs=%s", step_name, inputs)

                # running event handler
                await workflow_context.set(
                    ReservedContextKeys.WORKFLOW_CURRENT_STEP_NAME,
                    step_name,
                    set_reserved=True,
                )
                await workflow_context.set(
                    ReservedContextKeys.WORKFLOW_CURRENT_STEP_INDEX,
                    index,
                    set_reserved=True,
                )
                result = await step(**inputs)

                # saving outputs to context
                logger.debug("step='%s' result=%s", step_name, result)
                await logged_gather(
                    *[
                        workflow_context.set(key=var_name, value=var_value)
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
                logger.error(
                    "workflow_context=%s",
                    await workflow_context.get_serialized_context(),
                )
                raise

            # Storing exception to be possibly handled by the error state
            exception_info = ExceptionInfo(
                exception_class=e.__class__,
                action_name=await workflow_context.get(
                    ReservedContextKeys.WORKFLOW_ACTION_NAME, WorkflowName
                ),
                step_name=await workflow_context.get(
                    ReservedContextKeys.WORKFLOW_CURRENT_STEP_NAME, ActionName
                ),
                serialized_traceback=traceback.format_exc(),
            )
            await workflow_context.set(
                ReservedContextKeys.EXCEPTION, exception_info, set_reserved=True
            )

            action = (
                None
                if action.on_error_action is None
                else workflow[action.on_error_action]
            )
        else:
            action = (
                None if action.next_action is None else workflow[action.next_action]
            )
        finally:
            start_from_index = 0
