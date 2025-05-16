from settings_library.rabbit import RabbitSettings

from ._models import LongRunningNamespace
from ._rpc.server import ServerRPCInterface
from .runners.base import BaseServerJobInterface


class Server:
    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        long_running_namespace: LongRunningNamespace,
        job_interface: BaseServerJobInterface,
    ) -> None:
        """Exposes an RPC interface on the server side to run jobs

        Arguments:
            rabbit_settings -- settings to connect to RabbitMQ
            long_running_namespace -- unique namespace for the long-running jobs (allows to regisrter multiple servicer for different pourposes)
            job_interface -- custom interface for hanlding the execition of the jobs
        """
        self.rpc_interface = ServerRPCInterface(
            rabbit_settings, long_running_namespace, job_interface
        )

    async def setup(self) -> None:
        await self.rpc_interface.setup()

    async def teardown(self) -> None:
        await self.rpc_interface.teardown()
