variable "DOCKER_REGISTRY" {
  default = "itisfoundation"
}

variable "OSPARC_GATEWAY_SERVER_VERSION" {
  default = "latest"
}

target "osparc-gateway-server" {
    tags = ["${DOCKER_REGISTRY}/osparc-gateway-server:latest","${DOCKER_REGISTRY}/osparc-gateway-server:${OSPARC_GATEWAY_SERVER_VERSION}"]
    output = ["type=registry"]
}
