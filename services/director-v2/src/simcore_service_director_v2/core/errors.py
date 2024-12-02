""" Defines the different exceptions that may arise in the director


TODO: Exceptions should provide all info to create Error instances of the API model
For instance, assume there is a ficticious exception class FieldValidationError, then it would
translate into something like

// response - 422
{
  "error": {
    "status": 422,
    "error": "FIELDS_VALIDATION_ERROR",
    "description": "One or more fields raised validation errors."
    "fields": {
      "email": "Invalid email address.",
      "password": "Password too short."
    }
  }
}
"""

from typing import Any

from common_library.errors_classes import OsparcErrorMixin
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID


class DirectorError(OsparcErrorMixin, RuntimeError):
    msg_template: str = "Director-v2 unexpected error"


class ConfigurationError(DirectorError):
    msg_template: str = "Application misconfiguration: {msg}"


class UserNotFoundError(DirectorError):
    msg_template: str = "user {user_id} not found"


class ProjectNotFoundError(DirectorError):
    msg_template: str = "project {project_id} not found"


class ProjectNetworkNotFoundError(DirectorError):
    msg_template: str = "no networks found for project {project_id}"


class PricingPlanUnitNotFoundError(DirectorError):
    msg_template: str = "pricing plan not found {msg}"


class PipelineNotFoundError(DirectorError):
    msg_template: str = "pipeline {pipeline_id} not found"


class ComputationalRunNotFoundError(DirectorError):
    msg_template = "Computational run not found"


class ComputationalTaskNotFoundError(DirectorError):
    msg_template = "Computational task {node_id} not found"


class WalletNotEnoughCreditsError(DirectorError):
    msg_template = "Wallet '{wallet_name}' has {wallet_credit_amount} credits."


#
# SCHEDULER ERRORS
#
class ComputationalSchedulerError(DirectorError):
    msg_template = "Computational scheduler unexpected error {msg}"


class InvalidPipelineError(ComputationalSchedulerError):
    msg_template = "Computational scheduler: Invalid configuration of pipeline {pipeline_id}: {msg}"


class TaskSchedulingError(ComputationalSchedulerError):
    msg_template = "Computational scheduler: Task {node_id} in project {project_id} could not be scheduled {msg}"

    def __init__(self, project_id: ProjectID, node_id: NodeID, **ctx: Any) -> None:
        super().__init__(project_id=project_id, node_id=node_id, **ctx)
        self.project_id = project_id
        self.node_id = node_id

    def get_errors(self) -> list[ErrorDict]:
        # default implementation
        return [
            {
                "loc": (
                    f"{self.project_id}",
                    f"{self.node_id}",
                ),
                "msg": f"{self.args[0]}",
                "type": self.code,
            },
        ]


class MissingComputationalResourcesError(
    TaskSchedulingError
):  # pylint: disable=too-many-ancestors
    msg_template = (
        "Service {service_name}:{service_version} cannot be scheduled "
        "on cluster {cluster_id}: task needs '{task_resources}', "
        "cluster has {cluster_resources}"
    )


class InsuficientComputationalResourcesError(
    TaskSchedulingError
):  # pylint: disable=too-many-ancestors
    msg_template: str = (
        "Insufficient computational resources to run {service_name}:{service_version} with {service_requested_resources} on cluster {cluster_id}."
        "Cluster available workers: {cluster_available_resources}"
        "TIP: Reduce service required resources or contact oSparc support"
    )


class PortsValidationError(TaskSchedulingError):  # pylint: disable=too-many-ancestors
    msg_template: str = (
        "Node {node_id} in {project_id} with ports having invalid values {errors_list}"
    )


class ComputationalSchedulerChangedError(ComputationalSchedulerError):
    msg_template = "The dask scheduler ID changed from '{original_scheduler_id}' to '{current_scheduler_id}'"


class ComputationalBackendNotConnectedError(ComputationalSchedulerError):
    msg_template = "The dask computational backend is not connected"


class ComputationalBackendNoS3AccessError(ComputationalSchedulerError):
    msg_template = "The S3 backend is not ready, please try again later"


class ComputationalBackendTaskNotFoundError(ComputationalSchedulerError):
    msg_template = (
        "The dask computational backend does not know about the task '{job_id}'"
    )


class ComputationalBackendTaskResultsNotReadyError(ComputationalSchedulerError):
    msg_template = "The task result is not ready yet for job '{job_id}'"


class ClustersKeeperNotAvailableError(ComputationalSchedulerError):
    msg_template = "clusters-keeper service is not available!"


class ComputationalBackendOnDemandNotReadyError(ComputationalSchedulerError):
    msg_template = (
        "The on demand computational cluster is not ready 'est. remaining time: {eta}'"
    )


#
# SCHEDULER/CLUSTER ERRORS
#
class ClusterNotFoundError(ComputationalSchedulerError):
    msg_template = "The cluster '{cluster_id}' not found"


class ClusterAccessForbiddenError(ComputationalSchedulerError):
    msg_template = "Insufficient rights to access cluster '{cluster_id}'"


class ClusterInvalidOperationError(ComputationalSchedulerError):
    msg_template = "Invalid operation on cluster '{cluster_id}'"


#
# SCHEDULER/CLIENT ERRORS
#


class DaskClientRequestError(ComputationalSchedulerError):
    msg_template = (
        "The dask client to cluster on '{endpoint}' did an invalid request '{error}'"
    )


class DaskClusterError(ComputationalSchedulerError):
    msg_template = "The dask cluster on '{endpoint}' encountered an error: '{error}'"


class DaskGatewayServerError(ComputationalSchedulerError):
    msg_template = "The dask gateway on '{endpoint}' encountered an error: '{error}'"


class DaskClientAcquisisitonError(ComputationalSchedulerError):
    msg_template = (
        "The dask client to cluster '{cluster}' encountered an error '{error}'"
    )
