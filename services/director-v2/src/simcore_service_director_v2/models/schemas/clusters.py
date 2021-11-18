from models_library.clusters import Cluster
from pydantic.types import PositiveInt


class ClusterOut(Cluster):
    connection_status_code: PositiveInt
