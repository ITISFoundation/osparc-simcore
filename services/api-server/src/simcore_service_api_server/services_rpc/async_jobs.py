from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient


class AsyncJobClient:

    def __init__(self, rabbitmq_rpc_client: RabbitMQRPCClient):
        self._rabbitmq_rpc_client = rabbitmq_rpc_client
