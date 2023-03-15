# pylint: disable=undefined-variable

# NOTE: this configuration is used by the dask-gateway-server
# it follows [traitlets](https://traitlets.readthedocs.io/en/stable/config.html) configuration files

# defines the backend to use with the gateway
c.DaskGateway.backend_class = "osparc_gateway_server.backend.osparc.OsparcBackend"  # type: ignore
# defines the password for 'simple' authentication
c.Authenticator.password = "asdf"  # type: ignore
# defines log levels
c.DaskGateway.log_level = "WARN"  # type: ignore
c.Proxy.log_level = "WARN"  # type: ignore
