from pydantic import ConfigDict

from ..emails import LowerCaseEmailStr
from ..services import ServiceDockerData, ServiceMetaData
from ..services_access import ServiceAccessRights
from ..services_resources import ServiceResourcesDict


class ServiceUpdate(ServiceMetaData, ServiceAccessRights):
    model_config = ConfigDict()


class ServiceGet(
    ServiceDockerData, ServiceAccessRights, ServiceMetaData
):  # pylint: disable=too-many-ancestors
    owner: LowerCaseEmailStr | None = None
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


ServiceResourcesGet = ServiceResourcesDict
