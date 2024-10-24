# pylint: disable=relative-beyond-top-level

import asyncio
import logging
from copy import deepcopy
from math import floor

from common_library.error_codes import create_error_code
from fastapi import FastAPI
from servicelib.logging_errors import create_troubleshotting_log_kwargs

from .....core.dynamic_services_settings.scheduler import (
    DynamicServicesSchedulerSettings,
)
from .....models.dynamic_services_scheduler import (
    DynamicSidecarStatus,
    SchedulerData,
    ServiceName,
)
from ...docker_api import (
    are_sidecar_and_proxy_services_present,
    is_dynamic_sidecar_stack_missing,
    update_scheduler_data_label,
)
from ...errors import GenericDockerError
from ._events import REGISTERED_EVENTS
from ._events_utils import attempt_pod_removal_and_data_saving

logger = logging.getLogger(__name__)


async def _apply_observation_cycle(
    scheduler: "DynamicSidecarsScheduler",  # type: ignore  # noqa: F821
    scheduler_data: SchedulerData,
) -> None:
    """
    fetches status for service and then processes all the registered events
    and updates the status back
    """
    app: FastAPI = scheduler.app
    settings: DynamicServicesSchedulerSettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
    )
    initial_status = deepcopy(scheduler_data.dynamic_sidecar.status)

    if (  # do not refactor, second part of "and condition" is skipped most times
        scheduler_data.dynamic_sidecar.were_containers_created
        and not await are_sidecar_and_proxy_services_present(
            node_uuid=scheduler_data.node_uuid,
            swarm_stack_name=settings.SWARM_STACK_NAME,
        )
    ):
        # NOTE: once marked for removal the observation cycle needs
        # to continue in order for the service to be removed
        logger.warning(
            "Removing service %s from observation", scheduler_data.service_name
        )
        await scheduler.mark_service_for_removal(
            node_uuid=scheduler_data.node_uuid,
            can_save=scheduler_data.dynamic_sidecar.were_containers_created,
            skip_observation_recreation=True,
        )

    for dynamic_scheduler_event in REGISTERED_EVENTS:
        if await dynamic_scheduler_event.will_trigger(
            app=app, scheduler_data=scheduler_data
        ):
            # event.action will apply changes to the output_scheduler_data
            await dynamic_scheduler_event.action(app, scheduler_data)

    # check if the status of the services has changed from OK
    if initial_status != scheduler_data.dynamic_sidecar.status:
        logger.info(
            "Service %s overall status changed to %s",
            scheduler_data.service_name,
            scheduler_data.dynamic_sidecar.status,
        )


def _trigger_every_30_seconds(observation_counter: int, wait_interval: float) -> bool:
    # divisor to figure out if 30 seconds have passed based on the cycle count
    modulo_divisor = max(1, int(floor(30 / wait_interval)))
    return observation_counter % modulo_divisor == 0


async def observing_single_service(
    scheduler: "DynamicSidecarsScheduler",  # type: ignore
    service_name: ServiceName,
    scheduler_data: SchedulerData,
    dynamic_scheduler: DynamicServicesSchedulerSettings,
) -> None:
    app: FastAPI = scheduler.app

    if scheduler_data.dynamic_sidecar.status.current == DynamicSidecarStatus.FAILING:
        # potential use-cases:
        # 1. service failed on start -> it can be removed safely
        # 2. service must be deleted -> it can be removed safely
        # 3. service started and failed while running (either
        #   dy-sidecar, dy-proxy, or containers) -> it cannot be removed safely
        # 4. service started, and failed on closing -> it cannot be removed safely

        if scheduler_data.dynamic_sidecar.wait_for_manual_intervention_after_error:
            # use-cases: 3, 4
            # Since user data is important and must be saved, take no further
            # action and wait for manual intervention from support.

            # After manual intervention service can now be removed
            # from tracking.

            if (
                # NOTE: do not change below order, reduces pressure on the
                # docker swarm engine API.
                _trigger_every_30_seconds(
                    scheduler._observation_counter,  # pylint:disable=protected-access  # noqa: SLF001
                    dynamic_scheduler.DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL.total_seconds(),
                )
                and await is_dynamic_sidecar_stack_missing(
                    scheduler_data.node_uuid, dynamic_scheduler.SWARM_STACK_NAME
                )
            ):
                # if both proxy and sidecar ar missing at this point it
                # is safe to assume that user manually removed them from
                # Portainer after cleaning up.

                # NOTE: saving will fail since there is no dy-sidecar,
                # and the save was taken care of by support. Disabling it.
                scheduler_data.dynamic_sidecar.service_removal_state.can_save = False
                await attempt_pod_removal_and_data_saving(app, scheduler_data)

            return

        # use-cases: 1, 2
        # Cleanup all resources related to the dynamic-sidecar.
        await attempt_pod_removal_and_data_saving(app, scheduler_data)
        return

    scheduler_data_copy: SchedulerData = deepcopy(scheduler_data)
    try:
        await _apply_observation_cycle(scheduler, scheduler_data)
        logger.debug("completed observation cycle of %s", f"{service_name=}")
    except asyncio.CancelledError:  # pylint: disable=try-except-raise
        raise  # pragma: no cover
    except Exception as exc:  # pylint: disable=broad-except
        service_name = scheduler_data.service_name

        # With unhandled errors, let's generate and ID and send it to the end-user
        # so that we can trace the logs and debug the issue.
        user_error_msg = (
            f"This service ({service_name}) unexpectedly failed."
            " Our team has recorded the issue and is working to resolve it as quickly as possible."
            " Thank you for your patience."
        )
        error_code = create_error_code(exc)

        logger.exception(
            **create_troubleshotting_log_kwargs(
                user_error_msg,
                error=exc,
                error_context={
                    "service_name": service_name,
                    "user_id": scheduler_data.user_id,
                },
                error_code=error_code,
                tip=f"Observation of {service_name=} unexpectedly failed",
            )
        )
        scheduler_data.dynamic_sidecar.status.update_failing_status(
            # This message must be human-friendly
            user_error_msg,
            error_code,
        )
    finally:
        if scheduler_data_copy != scheduler_data:
            try:
                await update_scheduler_data_label(scheduler_data)
            except GenericDockerError as exc:
                logger.warning("Skipped labels update, please check:\n %s", f"{exc}")
