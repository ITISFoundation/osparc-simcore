from settings_library.rabbit import RabbitSettings

from ._models import LongRunningNamespace
from ._rpc.server import ServerRPCInterface
from .runners.base import BaseServerJobInterface


class Server:
    """
    Server for executing and managing long-running jobs requested by remote clients.

    This class provides the server-side counterpart to the Client, responsible for:

    1. Registering job handlers that can process long-running tasks
    2. Receiving and validating job requests via RabbitMQ
    3. Managing job execution lifecycle (start, status tracking, result storage)
    4. Providing job status updates to clients
    5. Handling graceful job termination during server shutdown

    Internally, the server relies on:
    - RPC Interface: Manages communication and request handling via RabbitMQ
    - Job Interface: Custom implementation that defines how jobs are executed

    The server workflow:
    1. Register job handlers during initialization
    2. Listen for incoming job requests on specified RabbitMQ queues
    3. Validate incoming job parameters
    4. Execute jobs in a managed context
    5. Track job status and store results
    6. Respond to client status and result queries
    7. Clean up resources when jobs complete or are terminated

    This design allows the server to handle multiple concurrent job requests
    while maintaining job state and providing resilience against server restarts.
    """

    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        long_running_namespace: LongRunningNamespace,
        job_interface: BaseServerJobInterface,
    ) -> None:
        self._rpc_interface = ServerRPCInterface(
            rabbit_settings, long_running_namespace, job_interface
        )

    # TODO: register jobs! and then use the interface to run them!!!

    async def setup(self) -> None:
        await self._rpc_interface.setup()

    async def teardown(self) -> None:
        await self._rpc_interface.teardown()
