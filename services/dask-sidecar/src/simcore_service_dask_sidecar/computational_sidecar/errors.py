class ComputationalSidecarException(Exception):
    """Basic exception"""


class ServiceRunError(ComputationalSidecarException):
    """Error in the runned service"""

    def __init__(
        self,
        service_key: str,
        service_version: str,
        container_id: str,
        exit_code: int,
        service_logs: str,
    ) -> None:
        super().__init__(
            f"The service {service_key}:{service_version} running "
            f"in container {container_id} failed with exit code {exit_code}\n"
            f"last logs: {service_logs}"
        )
