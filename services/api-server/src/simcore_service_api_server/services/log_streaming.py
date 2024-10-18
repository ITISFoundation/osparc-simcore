import asyncio
import logging
from asyncio import Queue
from collections.abc import AsyncIterable
from typing import Final

from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.users import UserID
from pydantic import NonNegativeInt
from servicelib.error_codes import create_error_code
from servicelib.logging_utils import log_catch
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_api_server.exceptions.backend_errors import BaseBackEndError
from simcore_service_api_server.models.schemas.errors import ErrorGet

from .._constants import MSG_INTERNAL_ERROR_USER_FRIENDLY_TEMPLATE
from ..exceptions.log_streaming_errors import (
    LogStreamerNotRegisteredError,
    LogStreamerRegistionConflictError,
)
from ..models.schemas.jobs import JobID, JobLog
from .director_v2 import DirectorV2Api

_logger = logging.getLogger(__name__)

_NEW_LINE: Final[str] = "\n"


class LogDistributor:
    def __init__(self, rabbitmq_client: RabbitMQClient):
        self._rabbit_client = rabbitmq_client
        self._log_streamers: dict[JobID, Queue[JobLog]] = {}
        self._queue_name: str

    async def setup(self):
        self._queue_name = await self._rabbit_client.subscribe(
            LoggerRabbitMessage.get_channel_name(),
            self._distribute_logs,
            exclusive_queue=True,
            topics=[],
        )

    async def teardown(self):
        await self._rabbit_client.unsubscribe(self._queue_name)

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.teardown()

    async def _distribute_logs(self, data: bytes):
        with log_catch(_logger, reraise=False):
            got = LoggerRabbitMessage.model_validate_json(data)
            item = JobLog(
                job_id=got.project_id,
                node_id=got.node_id,
                log_level=got.log_level,
                messages=got.messages,
            )
            queue = self._log_streamers.get(item.job_id)
            if queue is None:
                msg = f"Could not forward log because a logstreamer associated with job_id={item.job_id} was not registered"
                raise LogStreamerNotRegisteredError(job_id=item.job_id, details=msg)
            await queue.put(item)
            return True
        return False

    async def register(self, job_id: JobID, queue: Queue[JobLog]):
        if job_id in self._log_streamers:
            raise LogStreamerRegistionConflictError(job_id=job_id)
        self._log_streamers[job_id] = queue
        await self._rabbit_client.add_topics(
            LoggerRabbitMessage.get_channel_name(), topics=[f"{job_id}.*"]
        )

    async def deregister(self, job_id: JobID):
        if job_id not in self._log_streamers:
            msg = f"No stream was connected to {job_id}."
            raise LogStreamerNotRegisteredError(details=msg, job_id=job_id)
        await self._rabbit_client.remove_topics(
            LoggerRabbitMessage.get_channel_name(), topics=[f"{job_id}.*"]
        )
        del self._log_streamers[job_id]

    @property
    def get_log_queue_sizes(self) -> dict[JobID, int]:
        return {k: v.qsize() for k, v in self._log_streamers.items()}


class LogStreamer:
    def __init__(
        self,
        *,
        user_id: UserID,
        director2_api: DirectorV2Api,
        job_id: JobID,
        log_distributor: LogDistributor,
        log_check_timeout: NonNegativeInt,
    ):
        self._user_id = user_id
        self._director2_api = director2_api
        self._queue: Queue[JobLog] = Queue()
        self._job_id: JobID = job_id
        self._log_distributor: LogDistributor = log_distributor
        self._log_check_timeout: NonNegativeInt = log_check_timeout

    async def _project_done(self) -> bool:
        task = await self._director2_api.get_computation(
            project_id=self._job_id, user_id=self._user_id
        )
        return task.stopped is not None

    async def log_generator(self) -> AsyncIterable[str]:
        try:
            await self._log_distributor.register(self._job_id, self._queue)
            done: bool = False
            while not done:
                try:
                    log: JobLog = await asyncio.wait_for(
                        self._queue.get(), timeout=self._log_check_timeout
                    )
                    yield log.model_dump_json() + _NEW_LINE
                except asyncio.TimeoutError:
                    done = await self._project_done()
        except BaseBackEndError as exc:
            _logger.info("%s", f"{exc}")
            yield ErrorGet(errors=[f"{exc}"]).model_dump_json() + _NEW_LINE
        except Exception as exc:  # pylint: disable=W0718
            error_code = create_error_code(exc)
            _logger.exception(
                "Unexpected %s: %s",
                exc.__class__.__name__,
                f"{exc}",
                extra={"error_code": error_code},
            )
            yield ErrorGet(
                errors=[
                    MSG_INTERNAL_ERROR_USER_FRIENDLY_TEMPLATE + f" (OEC: {error_code})"
                ]
            ).model_dump_json() + _NEW_LINE
        finally:
            await self._log_distributor.deregister(self._job_id)
