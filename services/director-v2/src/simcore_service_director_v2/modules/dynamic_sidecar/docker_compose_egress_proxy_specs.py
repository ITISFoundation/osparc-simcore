import logging
from typing import Any

import yaml
from models_library.service_settings_labels import ComposeSpecLabel
from servicelib.docker_constants import SUFFIX_EGRESS_PROXY_NAME

logger = logging.getLogger(__name__)


YAML_PROXY_CFG = """
static_resources:
  listeners:
    - name: listener_0
      address:
        socket_address:
          address: 0.0.0.0
          port_value: 27000
      filter_chains:
        - filters:
            - name: envoy.filters.network.tcp_proxy
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.tcp_proxy.v3.TcpProxy
                stat_prefix: destination
                cluster: cluster_0
    - name: listener_1
      address:
        socket_address:
          address: 0.0.0.0
          port_value: 56625
      filter_chains:
        - filters:
            - name: envoy.filters.network.tcp_proxy
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.tcp_proxy.v3.TcpProxy
                stat_prefix: destination
                cluster: cluster_1
    - name: listener_2
      address:
        socket_address:
          address: 0.0.0.0
          port_value: 443
      filter_chains:
        - filters:
            - name: envoy.filters.network.tcp_proxy
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.tcp_proxy.v3.TcpProxy
                stat_prefix: destination
                cluster: cluster_2

  clusters:
    - name: cluster_0
      connect_timeout: 30s
      type: LOGICAL_DNS
      dns_lookup_family: V4_ONLY
      typed_dns_resolver_config:
        name: envoy.network.dns_resolver.cares
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.network.dns_resolver.cares.v3.CaresDnsResolverConfig
          resolvers:
            - socket_address:
                address: "172.16.8.15"
                port_value: 53
          dns_resolver_options:
            use_tcp_for_dns_lookups: true
            no_default_search_domain: true
      load_assignment:
        cluster_name: cluster_0
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: license.speag.com
                      port_value: 27000

    - name: cluster_1
      connect_timeout: 30s
      type: LOGICAL_DNS
      dns_lookup_family: V4_ONLY
      typed_dns_resolver_config:
        name: envoy.network.dns_resolver.cares
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.network.dns_resolver.cares.v3.CaresDnsResolverConfig
          resolvers:
            - socket_address:
                address: "172.16.8.15"
                port_value: 53
          dns_resolver_options:
            use_tcp_for_dns_lookups: true
            no_default_search_domain: true
      load_assignment:
        cluster_name: cluster_1
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: license.speag.com
                      port_value: 56625
    - name: cluster_2
      connect_timeout: 30s
      type: LOGICAL_DNS
      dns_lookup_family: V4_ONLY
      typed_dns_resolver_config:
        name: envoy.network.dns_resolver.cares
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.network.dns_resolver.cares.v3.CaresDnsResolverConfig
          resolvers:
            - socket_address:
                address: "8.8.8.8"
                port_value: 53
          dns_resolver_options:
            use_tcp_for_dns_lookups: true
            no_default_search_domain: true
      load_assignment:
        cluster_name: cluster_2
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: github.com
                      port_value: 443
"""


def add_egress_configuration(
    service_spec: ComposeSpecLabel,
    dynamic_sidecar_network_name: str,
    swarm_network_name: str,
) -> None:
    """
    Based on the product in the deployment, a service
    may be allowed or not to access external services.
    When a service is not allowed to access external services,
    there are usually a list of whitelisted domains that it needs to
    access. These are whitelisted per deployment.
    """
    # TODO: refactor using pydantic models

    # log level for this service should be disabled
    EGRESS_PROXY_DICT: dict[str, Any] = {
        "image": "envoyproxy/envoy:v1.24-latest",
        "command": f"envoy --log-level warning --config-yaml '{YAML_PROXY_CFG}'",
        "networks": {
            swarm_network_name: None,
            dynamic_sidecar_network_name: {
                "aliases": [
                    "github.com",
                    "license.speag.com",
                    "osparc.io",
                    "google.com",
                ]
            },
        },
    }

    logger.debug("YAML CONFIG:\n%s", yaml.safe_dump(EGRESS_PROXY_DICT))
    service_spec["services"][f"{SUFFIX_EGRESS_PROXY_NAME}1"] = EGRESS_PROXY_DICT


# NOTES:
# - usesing TCP forward is simple
# - UDP forward is complex, proxy needs to keep track of packet state since udp is stateless
#     https://www.envoyproxy.io/docs/envoy/latest/configuration/listeners/udp_filters/udp_proxy
# - will require multiple proxies per domain if the same port is used
