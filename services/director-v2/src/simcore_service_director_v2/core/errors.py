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

from common_library.errors_classes import OsparcErrorMixin
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID


class DirectorError(OsparcErrorMixin, RuntimeError):
    msg_template: str = "Director-v2 unexpected error"


class ConfigurationError(DirectorError):
    msg_template: str = "Application misconfiguration: {msg}"


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
    msg_template = "Computational scheduler unexpected error"


class InvalidPipelineError(ComputationalSchedulerError):
    msg_template = "Computational scheduler: Invalid configuration of pipeline {pipeline_id}: {msg}"


class TaskSchedulingError(ComputationalSchedulerError):
    msg_template = "Computational scheduler: Task {node_id} in project {project_id} could not be scheduled {msg}"


class MissingComputationalResourcesError(TaskSchedulingError):
    msg_template = (
        "Service {service_name}:{service_version} cannot be scheduled "
        "on cluster {cluster_id}: task needs '{task_resources}', "
        "cluster has {cluster_resources}",
    )


class InsuficientComputationalResourcesError(TaskSchedulingError):
    msg_template: str = (
        "Insufficient computational resources to run {service_name}:{service_version} with {service_requested_resources} on cluster {cluster_id}."
        "Cluster available workers: {cluster_available_resources}"
        "TIP: Reduce service required resources or contact oSparc support"
    )


class PortsValidationError(TaskSchedulingError):
    """
    Gathers all validation errors raised while checking input/output
    ports in a project's node.
    """

    def __init__(self, project_id: ProjectID, node_id: NodeID, errors: list[ErrorDict]):
        super().__init__(
            project_id,
            node_id,
            msg=f"Node with {len(errors)} ports having invalid values",
        )
        self.errors = errors

    def get_errors(self) -> list[ErrorDict]:
        """Returns 'public errors': filters only value_error.port_validation errors for the client.
        The rest only shown as number
        """
        value_errors: list[ErrorDict] = []
        for error in self.errors:
            # NOTE: should I filter? if error["type"].startswith("value_error."):

            loc_tail: list[str] = []
            if port_key := error.get("ctx", {}).get("port_key"):
                loc_tail.append(f"{port_key}")

            if schema_error_path := error.get("ctx", {}).get("schema_error_path"):
                loc_tail += list(schema_error_path)

            # WARNING: error in a node, might come from the previous node's port
            # DO NOT remove project/node/port hiearchy
            value_errors.append(
                {
                    "loc": (f"{self.project_id}", f"{self.node_id}", *tuple(loc_tail)),
                    "msg": error["msg"],
                    # NOTE: here we list the codes of the PydanticValueErrors collected in ValidationError
                    "type": error["type"],
                }
            )
        return value_errors


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
