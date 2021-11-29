# Configuration file for dask-gateway-server.

# ------------------------------------------------------------------------------
# Application(SingletonConfigurable) configuration
# ------------------------------------------------------------------------------
## This is an application.

## The date format used by logging formatters for %(asctime)s
#  Default: '%Y-%m-%d %H:%M:%S'
# c.Application.log_datefmt = '%Y-%m-%d %H:%M:%S'

## The Logging format template
#  Default: '%(log_color)s[%(levelname)1.1s %(asctime)s.%(msecs).03d %(name)s]%(reset)s %(message)s'
# c.Application.log_format = '%(log_color)s[%(levelname)1.1s %(asctime)s.%(msecs).03d %(name)s]%(reset)s %(message)s'

## Set the log level by value or name.
#  Choices: any of [0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL']
#  Default: 'INFO'
# c.Application.log_level = 'INFO'

## Instead of starting the Application, dump configuration to stdout
#  Default: False
# c.Application.show_config = False

## Instead of starting the Application, dump configuration to stdout (as JSON)
#  Default: False
# c.Application.show_config_json = False

# ------------------------------------------------------------------------------
# DaskGateway(Application) configuration
# ------------------------------------------------------------------------------
## A gateway for managing dask clusters across multiple users

## The address the private api server should *listen* at.
#
#  Should be of the form ``{hostname}:{port}``
#
#  Where:
#
#  - ``hostname`` sets the hostname to *listen* at. Set to ``""`` or
#    ``"0.0.0.0"`` to listen on all interfaces.
#  - ``port`` sets the port to *listen* at.
#
#  Defaults to ``127.0.0.1:0``.
#  Default: ''
# c.DaskGateway.address = "0.0.0.0:50000"
## User options for configuring an individual cluster.
#
#  Allows users to specify configuration overrides when creating a new cluster.
#  See the documentation for more information:
#
#  :doc:`cluster-options`.
#  Default: traitlets.Undefined
from dask_gateway_server.options import Float, Integer, Mapping, Options

c.Proxy.address = "0.0.0.0:50001"

## The gateway authenticator class to use
#  Default: 'dask_gateway_server.auth.SimpleAuthenticator'
c.DaskGateway.authenticator_class = "dask_gateway_server.auth.SimpleAuthenticator"
c.SimpleAuthenticator.password = "qweqwe"

## The gateway backend class to use
#  Default: 'dask_gateway_server.backends.base.Backend'
# c.DaskGateway.backend_class = "dask_gateway_server.backends.inprocess.InProcessBackend"

## The config file to load
#  Default: 'dask_gateway_config.py'
# c.DaskGateway.config_file = 'dask_gateway_config.py'

## The date format used by logging formatters for %(asctime)s
#  See also: Application.log_datefmt
# c.DaskGateway.log_datefmt = '%Y-%m-%d %H:%M:%S'

## The Logging format template
#  See also: Application.log_format
# c.DaskGateway.log_format = '%(log_color)s[%(levelname)1.1s %(asctime)s.%(msecs).03d %(name)s]%(reset)s %(message)s'

## Set the log level by value or name.
#  See also: Application.log_level
# c.DaskGateway.log_level = "DEBUG"

## Instead of starting the Application, dump configuration to stdout
#  See also: Application.show_config
# c.DaskGateway.show_config = False

## Instead of starting the Application, dump configuration to stdout (as JSON)
#  See also: Application.show_config_json
# c.DaskGateway.show_config_json = False

# ------------------------------------------------------------------------------
# Backend(LoggingConfigurable) configuration
# ------------------------------------------------------------------------------
## Base class for defining dask-gateway backends.
#
#      Subclasses should implement the following methods:
#
#      - ``setup``
#      - ``cleanup``
#      - ``start_cluster``
#      - ``stop_cluster``
#      - ``on_cluster_heartbeat``

## The address that internal components (e.g. dask clusters) will use when
#  contacting the gateway.
#  Default: ''
# c.Backend.api_url = ''

## The cluster config class to use
#  Default: 'dask_gateway_server.backends.base.ClusterConfig'
# c.Backend.cluster_config_class = 'dask_gateway_server.backends.base.ClusterConfig'


# c.Backend.cluster_options = traitlets.Undefined
c.Backend.cluster_options = Options(
    Float("CPU", default=12),
    Float("GPU", 1),
    Integer("RAM", 16 * 1024 ** 3),
    Mapping("maximas", default={"CPU": 12, "GPU": 1, "RAM": 1024 ** 3}),
)

# ------------------------------------------------------------------------------
# Authenticator(LoggingConfigurable) configuration
# ------------------------------------------------------------------------------
## Base class for authenticators.
#
#      An authenticator manages authenticating user API requests.
#
#      Subclasses must define ``authenticate``, and may optionally also define
#      ``setup``, ``cleanup`` and ``pre_response``.

## The maximum time in seconds to cache authentication information.
#
#          Helps reduce load on the backing authentication service by caching
#          responses between requests. After this time the user will need to be
#          reauthenticated before making additional requests (note this is usually
#          transparent to the user).
#  Default: 300
# c.Authenticator.cache_max_age = 300

## The cookie name to use for caching authentication information.
#  Default: ''
# c.Authenticator.cookie_name = ''
