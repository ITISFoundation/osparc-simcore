"""Defines the different exceptions that may arise in the clusters subpackage"""

from typing import Optional


class ClustersException(Exception):
    """Basic exception for errors raised in clusters"""

    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Unexpected error occured in clusters subpackage")


class ClusterNotFoundError(ClustersException):
    """Cluster was not found in DB"""

    def __init__(self, cluster_id: int):
        super().__init__(f"Cluster with id {cluster_id} not found")
        self.cluster_id = cluster_id


class ClusterAccessForbidden(ClustersException):
    """Cluster access is forbidden"""

    def __init__(self, cluster_id: int, msg: Optional[str] = None):
        super().__init__(
            f"Insufficient rights to access cluster with id {cluster_id}{f': {msg}' if msg else ''}"
        )
        self.cluster_id = cluster_id
