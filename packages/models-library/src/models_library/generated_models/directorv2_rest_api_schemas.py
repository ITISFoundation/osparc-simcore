# generated by datamodel-codegen:
#   filename:  openapi.json
#   timestamp: 2022-05-23T17:42:28+00:00

from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Union
from uuid import UUID

from pydantic import AnyUrl, BaseModel, EmailStr, Extra, Field, SecretStr


class Author(BaseModel):
    class Config:
        extra = Extra.forbid

    name: str = Field(
        ..., description="Name of the author", example="Jim Knopf", title="Name"
    )
    email: EmailStr = Field(..., description="Email address", title="Email")
    affiliation: Optional[str] = Field(
        None, description="Affiliation of the author", title="Affiliation"
    )


class Badge(BaseModel):
    class Config:
        extra = Extra.forbid

    name: str = Field(..., description="Name of the subject", title="Name")
    image: AnyUrl = Field(
        ...,
        description="Url to the badge",
        max_length=2083,
        min_length=1,
        title="Image",
    )
    url: AnyUrl = Field(
        ...,
        description="Link to the status",
        max_length=2083,
        min_length=1,
        title="Url",
    )


class BootChoice(BaseModel):
    label: str = Field(..., title="Label")
    description: str = Field(..., title="Description")


class BootOption(BaseModel):
    label: str = Field(..., title="Label")
    description: str = Field(..., title="Description")
    default: str = Field(..., title="Default")
    items: dict[str, BootChoice] = Field(..., title="Items")


class ClusterAccessRights(BaseModel):
    class Config:
        extra = Extra.forbid

    read: bool = Field(
        ..., description="allows to run pipelines on that cluster", title="Read"
    )
    write: bool = Field(..., description="allows to modify the cluster", title="Write")
    delete: bool = Field(..., description="allows to delete a cluster", title="Delete")


class ClusterType(Enum):
    """
    An enumeration.
    """

    AWS = "AWS"
    ON_PREMISE = "ON_PREMISE"


class ComputationCreate(BaseModel):
    user_id: int = Field(..., gt=0, title="User Id")
    project_id: UUID = Field(..., title="Project Id")
    start_pipeline: Optional[bool] = Field(
        False,
        description="if True the computation pipeline will start right away",
        title="Start Pipeline",
    )
    subgraph: Optional[list[UUID]] = Field(
        None,
        description="An optional set of nodes that must be executed, if empty the whole pipeline is executed",
        title="Subgraph",
    )
    force_restart: Optional[bool] = Field(
        False,
        description="if True will force re-running all dependent nodes",
        title="Force Restart",
    )
    cluster_id: Optional[int] = Field(
        None,
        description="the computation shall use the cluster described by its id, 0 is the default cluster",
        ge=0,
        title="Cluster Id",
    )


class ComputationDelete(BaseModel):
    user_id: int = Field(..., gt=0, title="User Id")
    force: Optional[bool] = Field(
        False,
        description="if True then the pipeline will be removed even if it is running",
        title="Force",
    )


class ComputationStop(BaseModel):
    user_id: int = Field(..., gt=0, title="User Id")


class ContainerSpec(BaseModel):
    """
        Implements entries that can be overriden for https://docs.docker.com/engine/api/v1.41/#operation/ServiceCreate
    request body: TaskTemplate -> ContainerSpec
    """

    class Config:
        extra = Extra.forbid

    Command: list[str] = Field(
        ...,
        description="Used to override the container's command",
        max_items=2,
        min_items=1,
        title="Command",
    )


class DictModelStrPositiveFloat(BaseModel):
    pass

    class Config:
        extra = Extra.allow


class DynamicServiceCreate(BaseModel):
    service_key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        regex="^(simcore)/(services)/dynamic(/[\\w/-]+)+$",
        title="Service Key",
    )
    service_version: str = Field(
        ...,
        description="semantic version number of the node",
        regex="^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$",
        title="Service Version",
    )
    user_id: int = Field(..., gt=0, title="User Id")
    project_id: UUID = Field(..., title="Project Id")
    service_uuid: UUID = Field(..., title="Service Uuid")
    service_basepath: Optional[str] = Field(
        None,
        description="predefined path where the dynamic service should be served. If empty, the service shall use the root endpoint.",
        title="Service Basepath",
    )
    service_resources: dict[str, Any] = Field(..., title="Service Resources")


class Type(Enum):
    jupyterhub = "jupyterhub"


class JupyterHubTokenAuthentication(BaseModel):
    class Config:
        extra = Extra.forbid

    type: Optional[Type] = Field(Type.jupyterhub, title="Type")
    api_token: str = Field(..., title="Api Token")


class Type1(Enum):
    kerberos = "kerberos"


class KerberosAuthentication(BaseModel):
    class Config:
        extra = Extra.forbid

    type: Optional[Type1] = Field(Type1.kerberos, title="Type")


class Meta(BaseModel):
    name: str = Field(..., title="Name")
    version: str = Field(
        ...,
        regex="^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$",
        title="Version",
    )
    released: Optional[dict[str, str]] = Field(
        None,
        description="Maps every route's path tag with a released version",
        title="Released",
    )


class Type2(Enum):
    none = "none"


class NoAuthentication(BaseModel):
    class Config:
        extra = Extra.forbid

    type: Optional[Type2] = Field(Type2.none, title="Type")


class NodeRequirements(BaseModel):
    CPU: float = Field(
        ...,
        description="defines the required (maximum) CPU shares for running the services",
        gt=0.0,
        title="Cpu",
    )
    GPU: Optional[int] = Field(
        None,
        description="defines the required (maximum) GPU for running the services",
        ge=0,
        title="Gpu",
    )
    RAM: int = Field(
        ...,
        description="defines the required (maximum) amount of RAM for running the services in bytes",
        title="Ram",
    )
    MPI: Optional[int] = Field(
        None,
        description="defines whether a MPI node is required for running the services",
        ge=0,
        le=1,
        title="Mpi",
    )


class ResourceValue(BaseModel):
    limit: Union[int, float, str] = Field(..., title="Limit")
    reservation: Union[int, float, str] = Field(..., title="Reservation")


class PortKey(BaseModel):
    __root__: str = Field(..., regex="^[-_a-zA-Z0-9]+$")


class RetrieveDataIn(BaseModel):
    port_keys: list[PortKey] = Field(
        ..., description="The port keys to retrieve data from", title="Port Keys"
    )


class RetrieveDataOut(BaseModel):
    size_bytes: int = Field(
        ...,
        description="The amount of data transferred by the retrieve call",
        title="Size Bytes",
    )


class RetrieveDataOutEnveloped(BaseModel):
    data: RetrieveDataOut


class RunningState(Enum):
    """
        State of execution of a project's computational workflow

    SEE StateType for task state
    """

    UNKNOWN = "UNKNOWN"
    PUBLISHED = "PUBLISHED"
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    STARTED = "STARTED"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class ServiceBootType(Enum):
    """
    An enumeration.
    """

    V0 = "V0"
    V2 = "V2"


class ServiceBuildDetails(BaseModel):
    build_date: str = Field(..., title="Build Date")
    vcs_ref: str = Field(..., title="Vcs Ref")
    vcs_url: str = Field(..., title="Vcs Url")


class ServiceExtras(BaseModel):
    node_requirements: NodeRequirements
    service_build_details: Optional[ServiceBuildDetails] = None
    container_spec: Optional[ContainerSpec] = None


class ServiceExtrasEnveloped(BaseModel):
    data: ServiceExtras


class ServiceState(Enum):
    """
    An enumeration.
    """

    pending = "pending"
    pulling = "pulling"
    starting = "starting"
    running = "running"
    complete = "complete"
    failed = "failed"


class ServiceType(Enum):
    """
    An enumeration.
    """

    computational = "computational"
    dynamic = "dynamic"
    frontend = "frontend"
    backend = "backend"


class Type4(Enum):
    simple = "simple"


class SimpleAuthentication(BaseModel):
    class Config:
        extra = Extra.forbid

    type: Optional[Type4] = Field(Type4.simple, title="Type")
    username: str = Field(..., title="Username")
    password: SecretStr = Field(..., title="Password")


class Structure(BaseModel):
    class Config:
        extra = Extra.forbid

    key: Union[str, bool, float] = Field(..., title="Key")
    label: str = Field(..., title="Label")


class TaskLogFileGet(BaseModel):
    task_id: UUID = Field(..., title="Task Id")
    download_link: Optional[AnyUrl] = Field(
        None,
        description="Presigned link for log file or None if still not available",
        max_length=65536,
        min_length=1,
        title="Download Link",
    )


class TextArea(BaseModel):
    class Config:
        extra = Extra.forbid

    minHeight: int = Field(
        ..., description="minimum Height of the textarea", gt=0, title="Minheight"
    )


class UsedResources(BaseModel):
    pass

    class Config:
        extra = Extra.allow


class ValidationError(BaseModel):
    loc: list[str] = Field(..., title="Location")
    msg: str = Field(..., title="Message")
    type: str = Field(..., title="Error Type")


class WidgetType(Enum):
    """
    An enumeration.
    """

    TextArea = "TextArea"
    SelectBox = "SelectBox"


class WorkerMetrics(BaseModel):
    cpu: float = Field(..., description="consumed % of cpus", title="Cpu")
    memory: int = Field(..., description="consumed memory", title="Memory")
    num_fds: int = Field(..., description="consumed file descriptors", title="Num Fds")
    ready: int = Field(..., description="# tasks ready to run", ge=0, title="Ready")
    executing: int = Field(
        ..., description="# tasks currently executing", ge=0, title="Executing"
    )
    in_flight: int = Field(
        ..., description="# tasks waiting for data", ge=0, title="In Flight"
    )
    in_memory: int = Field(
        ..., description="# tasks in worker memory", ge=0, title="In Memory"
    )


class WorkersDict(BaseModel):
    pass

    class Config:
        extra = Extra.allow


class ClusterCreate(BaseModel):
    class Config:
        extra = Extra.forbid

    name: str = Field(
        ..., description="The human readable name of the cluster", title="Name"
    )
    description: Optional[str] = Field(None, title="Description")
    type: ClusterType
    owner: Optional[int] = Field(None, gt=0, title="Owner")
    thumbnail: Optional[AnyUrl] = Field(
        None,
        description="url to the image describing this cluster",
        max_length=2083,
        min_length=1,
        title="Thumbnail",
    )
    endpoint: AnyUrl = Field(..., max_length=65536, min_length=1, title="Endpoint")
    authentication: Union[
        SimpleAuthentication, KerberosAuthentication, JupyterHubTokenAuthentication
    ] = Field(..., title="Authentication")
    accessRights: Optional[dict[str, ClusterAccessRights]] = Field(
        None, title="Accessrights"
    )


class ClusterGet(BaseModel):
    class Config:
        extra = Extra.forbid

    name: str = Field(
        ..., description="The human readable name of the cluster", title="Name"
    )
    description: Optional[str] = Field(None, title="Description")
    type: ClusterType
    owner: int = Field(..., gt=0, title="Owner")
    thumbnail: Optional[AnyUrl] = Field(
        None,
        description="url to the image describing this cluster",
        max_length=2083,
        min_length=1,
        title="Thumbnail",
    )
    endpoint: AnyUrl = Field(..., max_length=65536, min_length=1, title="Endpoint")
    authentication: Union[
        SimpleAuthentication,
        KerberosAuthentication,
        JupyterHubTokenAuthentication,
        NoAuthentication,
    ] = Field(..., description="Dask gateway authentication", title="Authentication")
    accessRights: Optional[dict[str, ClusterAccessRights]] = Field(
        None, title="Accessrights"
    )
    id: int = Field(..., description="The cluster ID", ge=0, title="Id")


class ClusterPatch(BaseModel):
    class Config:
        extra = Extra.forbid

    name: Optional[str] = Field(None, title="Name")
    description: Optional[str] = Field(None, title="Description")
    type: Optional[ClusterType] = None
    owner: Optional[int] = Field(None, gt=0, title="Owner")
    thumbnail: Optional[AnyUrl] = Field(
        None, max_length=2083, min_length=1, title="Thumbnail"
    )
    endpoint: Optional[AnyUrl] = Field(
        None, max_length=65536, min_length=1, title="Endpoint"
    )
    authentication: Optional[
        Union[
            SimpleAuthentication, KerberosAuthentication, JupyterHubTokenAuthentication
        ]
    ] = Field(None, title="Authentication")
    accessRights: Optional[dict[str, ClusterAccessRights]] = Field(
        None, title="Accessrights"
    )


class ClusterPing(BaseModel):
    endpoint: AnyUrl = Field(..., max_length=65536, min_length=1, title="Endpoint")
    authentication: Union[
        SimpleAuthentication,
        KerberosAuthentication,
        JupyterHubTokenAuthentication,
        NoAuthentication,
    ] = Field(..., description="Dask gateway authentication", title="Authentication")


class HTTPValidationError(BaseModel):
    errors: Optional[list[ValidationError]] = Field(None, title="Validation errors")


class ImageResources(BaseModel):
    image: str = Field(
        ...,
        description="Used by the frontend to provide a context for the users.Services with a docker-compose spec will have multiple entries.Using the `image:version` instead of the docker-compose spec is more helpful for the end user.",
        regex="[\\w/-]+:[\\w.@]+",
        title="Image",
    )
    resources: dict[str, ResourceValue] = Field(..., title="Resources")


class NodeState(BaseModel):
    class Config:
        extra = Extra.forbid

    modified: Optional[bool] = Field(
        True,
        description="true if the node's outputs need to be re-computed",
        title="Modified",
    )
    dependencies: Optional[list[UUID]] = Field(
        None,
        description="contains the node inputs dependencies if they need to be computed first",
        title="Dependencies",
        unique_items=True,
    )
    currentStatus: Optional[RunningState] = Field(
        RunningState.NOT_STARTED, description="the node's current state"
    )


class PipelineDetails(BaseModel):
    adjacency_list: dict[str, list[UUID]] = Field(
        ...,
        description="The adjacency list of the current pipeline in terms of {NodeID: [successor NodeID]}",
        title="Adjacency List",
    )
    node_states: dict[str, NodeState] = Field(
        ...,
        description="The states of each of the computational nodes in the pipeline",
        title="Node States",
    )


class RunningDynamicServiceDetails(BaseModel):
    service_key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        regex="^(simcore)/(services)/dynamic(/[\\w/-]+)+$",
        title="Service Key",
    )
    service_version: str = Field(
        ...,
        description="semantic version number of the node",
        regex="^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$",
        title="Service Version",
    )
    user_id: int = Field(..., gt=0, title="User Id")
    project_id: UUID = Field(..., title="Project Id")
    service_uuid: UUID = Field(..., title="Service Uuid")
    service_basepath: Optional[str] = Field(
        None,
        description="predefined path where the dynamic service should be served. If empty, the service shall use the root endpoint.",
        title="Service Basepath",
    )
    boot_type: Optional[ServiceBootType] = Field(
        ServiceBootType.V0,
        description="Describes how the dynamic services was started (legacy=V0, modern=V2).Since legacy services do not have this label it defaults to V0.",
    )
    service_host: str = Field(
        ..., description="the service swarm internal host name", title="Service Host"
    )
    service_port: int = Field(
        ...,
        description="the service swarm internal port",
        gt=0,
        lt=65535,
        title="Service Port",
    )
    published_port: Optional[int] = Field(
        None,
        description="the service swarm published port if any",
        gt=0,
        lt=65535,
        title="Published Port",
    )
    entry_point: Optional[str] = Field(
        None,
        description="if empty the service entrypoint is on the root endpoint.",
        title="Entry Point",
    )
    service_state: ServiceState = Field(..., description="service current state")
    service_message: Optional[str] = Field(
        None,
        description="additional information related to service state",
        title="Service Message",
    )


class RunningServiceDetails(BaseModel):
    published_port: Optional[int] = Field(
        None,
        description="The ports where the service provides its interface on the docker swarm",
        gt=0,
        lt=65535,
        title="Published Port",
    )
    entry_point: str = Field(
        ...,
        description="The entry point where the service provides its interface",
        title="Entry Point",
    )
    service_uuid: str = Field(
        ...,
        description="The node UUID attached to the service",
        regex="^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$",
        title="Service Uuid",
    )
    service_key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        example=[
            "simcore/services/comp/itis/sleeper",
            "simcore/services/dynamic/3dviewer",
        ],
        regex="^(simcore)/(services)/(comp|dynamic|frontend)(/[\\w/-]+)+$",
        title="Service Key",
    )
    service_version: str = Field(
        ...,
        description="service version number",
        example=["1.0.0", "0.0.1"],
        regex="^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$",
        title="Service Version",
    )
    service_host: str = Field(
        ..., description="service host name within the network", title="Service Host"
    )
    service_port: Optional[int] = Field(
        80,
        description="port to access the service within the network",
        gt=0,
        lt=65535,
        title="Service Port",
    )
    service_basepath: str = Field(
        ...,
        description="the service base entrypoint where the service serves its contents",
        title="Service Basepath",
    )
    service_state: ServiceState = Field(
        ...,
        description="the service state * 'pending' - The service is waiting for resources to start * 'pulling' - The service is being pulled from the registry * 'starting' - The service is starting * 'running' - The service is running * 'complete' - The service completed * 'failed' - The service failed to start",
    )
    service_message: str = Field(
        ..., description="the service message", title="Service Message"
    )


class RunningServicesDetailsArray(BaseModel):
    __root__: list[RunningServiceDetails] = Field(
        ..., title="RunningServicesDetailsArray"
    )


class RunningServicesDetailsArrayEnveloped(BaseModel):
    data: RunningServicesDetailsArray


class Scheduler(BaseModel):
    status: str = Field(
        ..., description="The running status of the scheduler", title="Status"
    )
    workers: Optional[WorkersDict] = None


class SelectBox(BaseModel):
    class Config:
        extra = Extra.forbid

    structure: list[Structure] = Field(..., min_items=1, title="Structure")


class ServiceDockerData(BaseModel):
    """
        Static metadata for a service injected in the image labels

    This is one to one with node-meta-v0.0.1.json
    """

    class Config:
        extra = Extra.forbid

    name: str = Field(
        ...,
        description="short, human readable name for the node",
        example="Fast Counter",
        title="Name",
    )
    thumbnail: Optional[AnyUrl] = Field(
        None,
        description="url to the thumbnail",
        max_length=2083,
        min_length=1,
        title="Thumbnail",
    )
    description: str = Field(
        ...,
        description="human readable description of the purpose of the node",
        title="Description",
    )
    key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        regex="^(simcore)/(services)/(comp|dynamic|frontend)(/[\\w/-]+)+$",
        title="Key",
    )
    version: str = Field(
        ...,
        description="service version number",
        regex="^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$",
        title="Version",
    )
    integration_version: Optional[str] = Field(
        None,
        alias="integration-version",
        description="integration version number",
        regex="^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$",
        title="Integration-Version",
    )
    type: ServiceType = Field(..., description="service type")
    badges: Optional[list[Badge]] = Field(None, title="Badges")
    authors: list[Author] = Field(..., min_items=1, title="Authors")
    contact: EmailStr = Field(
        ...,
        description="email to correspond to the authors about the node",
        title="Contact",
    )
    inputs: dict[str, Any] = Field(
        ..., description="definition of the inputs of this node", title="Inputs"
    )
    outputs: dict[str, Any] = Field(
        ..., description="definition of the outputs of this node", title="Outputs"
    )
    boot_options: Optional[dict[str, Any]] = Field(
        None,
        alias="boot-options",
        description="Service defined boot options. These get injected in the service as env variables.",
        title="Boot-Options",
    )


class ServicesArrayEnveloped(BaseModel):
    data: list[ServiceDockerData] = Field(..., title="Data")


class Widget(BaseModel):
    class Config:
        extra = Extra.forbid

    type: WidgetType = Field(..., description="type of the property")
    details: Union[TextArea, SelectBox] = Field(..., title="Details")


class Worker(BaseModel):
    id: str = Field(..., title="Id")
    name: str = Field(..., title="Name")
    resources: DictModelStrPositiveFloat
    used_resources: UsedResources
    memory_limit: int = Field(..., title="Memory Limit")
    metrics: WorkerMetrics


class ClusterDetailsGet(BaseModel):
    scheduler: Scheduler = Field(
        ...,
        description="This contains dask scheduler information given by the underlying dask library",
        title="Scheduler",
    )
    dashboard_link: AnyUrl = Field(
        ...,
        description="Link to this scheduler's dashboard",
        max_length=65536,
        min_length=1,
        title="Dashboard Link",
    )


class ComputationGet(BaseModel):
    id: UUID = Field(..., description="the id of the computation task", title="Id")
    state: RunningState = Field(..., description="the state of the computational task")
    result: Optional[str] = Field(
        None, description="the result of the computational task", title="Result"
    )
    pipeline_details: PipelineDetails = Field(
        ...,
        description="the details of the generated pipeline",
        title="Pipeline Details",
    )
    iteration: int = Field(
        ...,
        description="the iteration id of the computation task (none if no task ran yet)",
        gt=0,
        title="Iteration",
    )
    cluster_id: int = Field(
        ...,
        description="the cluster on which the computaional task runs/ran (none if no task ran yet)",
        ge=0,
        title="Cluster Id",
    )
    url: AnyUrl = Field(
        ...,
        description="the link where to get the status of the task",
        max_length=65536,
        min_length=1,
        title="Url",
    )
    stop_url: Optional[AnyUrl] = Field(
        None,
        description="the link where to stop the task",
        max_length=65536,
        min_length=1,
        title="Stop Url",
    )


class ServiceInput(BaseModel):
    """
    Metadata on a service input port
    """

    class Config:
        extra = Extra.forbid

    displayOrder: Optional[float] = Field(
        None,
        description="DEPRECATED: new display order is taken from the item position. This will be removed.",
        title="Displayorder",
    )
    label: str = Field(
        ..., description="short name for the property", example="Age", title="Label"
    )
    description: str = Field(
        ...,
        description="description of the property",
        example="Age in seconds since 1970",
        title="Description",
    )
    type: str = Field(
        ...,
        description="data type expected on this input glob matching for data type is allowed",
        regex="^(number|integer|boolean|string|ref_contentSchema|data:([^/\\s,]+/[^/\\s,]+|\\[[^/\\s,]+/[^/\\s,]+(,[^/\\s]+/[^/,\\s]+)*\\]))$",
        title="Type",
    )
    contentSchema: Optional[dict[str, Any]] = Field(
        None,
        description="jsonschema of this input/output. Required when type='ref_contentSchema'",
        title="Contentschema",
    )
    fileToKeyMap: Optional[dict[str, Any]] = Field(
        None,
        description="Place the data associated with the named keys in files",
        title="Filetokeymap",
    )
    unit: Optional[str] = Field(
        None, description="Units, when it refers to a physical quantity", title="Unit"
    )
    defaultValue: Optional[Union[bool, int, float, str]] = Field(
        None, title="Defaultvalue"
    )
    widget: Optional[Widget] = Field(
        None,
        description="custom widget to use instead of the default one determined from the data-type",
        title="Widget",
    )


class ServiceOutput(BaseModel):
    """
    Base class for service input/outputs
    """

    class Config:
        extra = Extra.forbid

    displayOrder: Optional[float] = Field(
        None,
        description="DEPRECATED: new display order is taken from the item position. This will be removed.",
        title="Displayorder",
    )
    label: str = Field(
        ..., description="short name for the property", example="Age", title="Label"
    )
    description: str = Field(
        ...,
        description="description of the property",
        example="Age in seconds since 1970",
        title="Description",
    )
    type: str = Field(
        ...,
        description="data type expected on this input glob matching for data type is allowed",
        regex="^(number|integer|boolean|string|ref_contentSchema|data:([^/\\s,]+/[^/\\s,]+|\\[[^/\\s,]+/[^/\\s,]+(,[^/\\s]+/[^/,\\s]+)*\\]))$",
        title="Type",
    )
    contentSchema: Optional[dict[str, Any]] = Field(
        None,
        description="jsonschema of this input/output. Required when type='ref_contentSchema'",
        title="Contentschema",
    )
    fileToKeyMap: Optional[dict[str, Any]] = Field(
        None,
        description="Place the data associated with the named keys in files",
        title="Filetokeymap",
    )
    unit: Optional[str] = Field(
        None, description="Units, when it refers to a physical quantity", title="Unit"
    )
    widget: Optional[Widget] = Field(
        None,
        description="custom widget to use instead of the default one determined from the data-type",
        title="Widget",
    )
