from enum import StrEnum


class SimcoreClusterOrchestrator(StrEnum):
    DOCKER_SWARM = "docker_swarm"
    K8S = "k8s"
