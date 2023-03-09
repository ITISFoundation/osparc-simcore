class OSparcGatewayServerException(Exception):
    """Exception raised when there is an exception in oSparc gateway server"""


class NoServiceTasksError(OSparcGatewayServerException):
    """Exception raised when there is no tasks attached to service"""


class TaskNotAssignedError(OSparcGatewayServerException):
    """Exception raised when a task is not assigned to a host"""


class NoHostFoundError(OSparcGatewayServerException):
    """Exception raised when there is no host found"""
