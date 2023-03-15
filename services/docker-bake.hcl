variable "DOCKER_REGISTRY" {
  default = "itisfoundation"
}

variable "DASK_SIDECAR_VERSION" {
  default = "latest"
}

target "dask-sidecar" {
    tags = ["${DOCKER_REGISTRY}/dask-sidecar:latest","${DOCKER_REGISTRY}/dask-sidecar:${DASK_SIDECAR_VERSION}"]
    output = ["type=registry"]
}

variable "OSPARC_GATEWAY_SERVER_VERSION" {
  default = "latest"
}

target "osparc-gateway-server" {
    tags = ["${DOCKER_REGISTRY}/osparc-gateway-server:latest","${DOCKER_REGISTRY}/osparc-gateway-server:${OSPARC_GATEWAY_SERVER_VERSION}"]
    output = ["type=registry"]
}
