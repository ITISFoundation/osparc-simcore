from models_library.api_schemas_catalog.services import MyServiceGet
from models_library.batch_operations import BatchGetEnvelope
from models_library.services import ServiceKeyVersion


class BatchGetUserServicesResult(BatchGetEnvelope[MyServiceGet, ServiceKeyVersion]):
    """
    batch-get result for services in the catalog
    """
