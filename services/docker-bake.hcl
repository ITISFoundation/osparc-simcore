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
