from ..domain.service import ServiceDockerData, ServiceCommonData, ServiceAccessRights


class ServiceOut(ServiceAccessRights, ServiceDockerData):
    pass


class ServiceIn(ServiceCommonData, ServiceAccessRights):
    pass
