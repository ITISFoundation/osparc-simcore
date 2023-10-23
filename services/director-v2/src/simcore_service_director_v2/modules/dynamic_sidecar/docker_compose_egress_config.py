import logging
from collections import deque
from dataclasses import dataclass
from typing import Any, Final

import yaml
from models_library.basic_types import PortInt
from models_library.osparc_variable_identifier import raise_if_unresolved
from models_library.service_settings_labels import (
    ComposeSpecLabelDict,
    SimcoreServiceLabels,
)
from models_library.service_settings_nat_rule import NATRule
from ordered_set import OrderedSet
from servicelib.docker_constants import SUFFIX_EGRESS_PROXY_NAME

from ...core.settings import DynamicSidecarEgressSettings

_DEFAULT_USER_SERVICES_NETWORK_WITH_INTERNET_NAME: Final[str] = "with-internet"


logger = logging.getLogger(__name__)


@dataclass
class _HostData:
    hostname: str
    dns_resolver_address: str
    dns_resolver_port: PortInt

    def __hash__(self) -> int:
        return hash((type(self),) + tuple(self.__dict__.values()))

    def __lt__(self, other: "_HostData") -> bool:
        return self.hostname < other.hostname


_ProxyRule = tuple[_HostData, PortInt]
_TCPListener = dict[str, Any]
_TCPCluster = dict[str, Any]


def _get_tcp_listener(
    name: str,
    port: PortInt,
    cluster_name: str,
) -> _TCPListener:
    """returns an Envoy proxy TCP listener configuration"""
    # NOTE: for details see Envoy's Dynamic forward proxy
    # https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/dynamic_forward_proxy_filter
    return {
        "name": name,
        "address": {
            "socket_address": {
                "address": "0.0.0.0",  # nosec
                "port_value": port,
            },
        },
        "filter_chains": [
            {
                "filters": [
                    {
                        "name": "envoy.filters.network.tcp_proxy",
                        "typed_config": {
                            "@type": "type.googleapis.com/envoy.extensions.filters.network.tcp_proxy.v3.TcpProxy",
                            "stat_prefix": "destination",
                            "cluster": cluster_name,
                        },
                    }
                ]
            },
        ],
    }


def _get_tcp_cluster(
    cluster_name: str, dns_address: str, dns_port: PortInt, hostname: str, port: PortInt
) -> _TCPCluster:
    """returns an Envoy proxy TCP cluster configuration"""
    # NOTE: for details see Envoy's Dynamic forward proxy
    # https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/dynamic_forward_proxy_filter
    return {
        "name": cluster_name,
        "connect_timeout": "30s",
        "type": "LOGICAL_DNS",
        "dns_lookup_family": "V4_ONLY",
        "typed_dns_resolver_config": {
            "name": "envoy.network.dns_resolver.cares",
            "typed_config": {
                "@type": "type.googleapis.com/envoy.extensions.network.dns_resolver.cares.v3.CaresDnsResolverConfig",
                "resolvers": [
                    {
                        "socket_address": {
                            "address": dns_address,
                            "port_value": dns_port,
                        }
                    }
                ],
                "dns_resolver_options": {
                    "use_tcp_for_dns_lookups": False,
                    "no_default_search_domain": True,
                },
            },
        },
        "load_assignment": {
            "cluster_name": cluster_name,
            "endpoints": [
                {
                    "lb_endpoints": [
                        {
                            "endpoint": {
                                "address": {
                                    "socket_address": {
                                        "address": hostname,
                                        "port_value": port,
                                    }
                                }
                            }
                        }
                    ]
                }
            ],
        },
    }


def _get_envoy_config(proxy_rules: OrderedSet[_ProxyRule]) -> dict[str, Any]:
    listeners: deque[_TCPListener] = deque()
    clusters: deque[_TCPCluster] = deque()

    for k, proxy_rule in enumerate(proxy_rules):
        host_data, port = proxy_rule

        listener_name = f"listener_{k}"
        cluster_name = f"cluster_{k}"

        listener = _get_tcp_listener(
            name=listener_name, port=port, cluster_name=cluster_name
        )
        cluster = _get_tcp_cluster(
            cluster_name=cluster_name,
            dns_address=host_data.dns_resolver_address,
            dns_port=host_data.dns_resolver_port,
            hostname=host_data.hostname,
            port=port,
        )

        listeners.append(listener)
        clusters.append(cluster)

    yaml_proxy_config: dict[str, Any] = {
        "static_resources": {
            "listeners": list(listeners),
            "clusters": list(clusters),
        },
    }
    return yaml_proxy_config


def _get_egress_proxy_network_name(egress_proxy_name: str) -> str:
    return egress_proxy_name


def _add_egress_proxy_network(
    service_spec: ComposeSpecLabelDict, egress_proxy_name: str
) -> None:
    networks = service_spec.get("networks", {})
    networks[_get_egress_proxy_network_name(egress_proxy_name)] = {"internal": True}
    service_spec["networks"] = networks


def _get_egress_proxy_service_config(
    egress_proxy_rules: OrderedSet[_ProxyRule],
    network_with_internet: str,
    egress_proxy_settings: DynamicSidecarEgressSettings,
    egress_proxy_name: str,
) -> dict[str, Any]:
    network_aliases: set[str] = {x[0].hostname for x in egress_proxy_rules}

    envoy_config: dict[str, Any] = _get_envoy_config(egress_proxy_rules)
    yaml_str_envoy_config: str = yaml.safe_dump(envoy_config, default_style='"')
    logger.debug("ENVOY CONFIG\n%s", yaml_str_envoy_config)

    command: str = " ".join(
        [
            "envoy",
            "--log-level",
            egress_proxy_settings.DYNAMIC_SIDECAR_ENVOY_LOG_LEVEL.to_log_level(),
            # add envoy proxy config
            "--config-yaml",
            f"'{yaml_str_envoy_config}'",
        ],
    )

    egress_proxy_config: dict[str, Any] = {
        "image": egress_proxy_settings.DYNAMIC_SIDECAR_ENVOY_IMAGE,
        "command": command,
        "networks": {
            # allows the proxy to access the internet
            network_with_internet: None,
            # allows containers to contact proxy via these aliases
            _get_egress_proxy_network_name(egress_proxy_name): {
                "aliases": list(network_aliases)
            },
        },
    }
    return egress_proxy_config


def _get_egress_proxy_dns_port_rules(
    all_host_permit_list_policies: list[NATRule],
) -> list[OrderedSet[_ProxyRule]]:
    """returns a list of sets of rules to be applied to each proxy"""
    # 1. map all ports to hostnames to compute overlapping ports per proxy
    port_to_hostname: dict[PortInt, set[_HostData]] = {}

    for host_permit_list_policy in all_host_permit_list_policies:
        for port in host_permit_list_policy.iter_tcp_ports():
            if port not in port_to_hostname:
                port_to_hostname[port] = OrderedSet()
            port_to_hostname[port].add(
                _HostData(
                    hostname=raise_if_unresolved(host_permit_list_policy.hostname),
                    dns_resolver_address=raise_if_unresolved(
                        host_permit_list_policy.dns_resolver.address
                    ),
                    dns_resolver_port=raise_if_unresolved(
                        host_permit_list_policy.dns_resolver.port
                    ),
                )
            )

    # 2. extract each single proxy rules
    grouped_proxy_rules: deque[OrderedSet[_ProxyRule]] = deque()
    while len(port_to_hostname) > 0:
        proxy_rules: OrderedSet[_ProxyRule] = OrderedSet()

        # size can change during iteration
        for port in OrderedSet(port_to_hostname.keys()):
            hostname = port_to_hostname[port].pop()
            proxy_rules.add((hostname, port))
            if len(port_to_hostname[port]) == 0:
                del port_to_hostname[port]

        grouped_proxy_rules.append(proxy_rules)

    return list(sorted(grouped_proxy_rules))


def _allow_outgoing_internet(
    service_spec: ComposeSpecLabelDict, container_name: str
) -> None:
    # containers are allowed complete access to the internet by
    # connecting them to an isolated network (from the rest
    # of the deployment)
    container_spec = service_spec["services"][container_name]
    networks = container_spec.get("networks", {})
    networks[_DEFAULT_USER_SERVICES_NETWORK_WITH_INTERNET_NAME] = None
    service_spec["services"][container_name]["networks"] = networks


def add_egress_configuration(
    service_spec: ComposeSpecLabelDict,
    simcore_service_labels: SimcoreServiceLabels,
    egress_proxy_settings: DynamicSidecarEgressSettings,
) -> None:
    """
    Each service defines rules to allow certain containers to gain access
    to the internet. The following are supported:
    - `simcore.service.containers-allowed-outgoing-permit-list` list of host
        and ports that are allowed to be connected
    - `simcore.service.containers-allowed-outgoing-internet` list of containers
        allowed to have complete access to the internet
    """

    # creating a network with internet access
    if (
        simcore_service_labels.containers_allowed_outgoing_internet
        or simcore_service_labels.containers_allowed_outgoing_permit_list
    ):
        # placing containers with internet access in an isolated network
        service_networks = service_spec.setdefault("networks", {})
        service_networks[_DEFAULT_USER_SERVICES_NETWORK_WITH_INTERNET_NAME] = {
            "internal": False
        }

    # allow complete internet access to single container
    if simcore_service_labels.containers_allowed_outgoing_internet:
        # attach to network
        for (
            container_name
        ) in simcore_service_labels.containers_allowed_outgoing_internet:
            _allow_outgoing_internet(service_spec, container_name)

    # allow internet access to containers based on DNS:PORT rules
    if simcore_service_labels.containers_allowed_outgoing_permit_list:
        # get all HostPermitListPolicy entries from all containers
        all_host_permit_list_policies: list[NATRule] = []

        hostname_port_to_container_name: dict[tuple[str, PortInt], str] = {}
        container_name_to_proxies_names: dict[str, set[str]] = {}

        for (
            container_name,
            host_permit_list_policies,
        ) in simcore_service_labels.containers_allowed_outgoing_permit_list.items():
            for host_permit_list_policy in host_permit_list_policies:
                all_host_permit_list_policies.append(host_permit_list_policy)

                for port in host_permit_list_policy.iter_tcp_ports():
                    hostname_port_to_container_name[
                        (
                            raise_if_unresolved(host_permit_list_policy.hostname),
                            port,
                        )
                    ] = container_name

        # assemble proxy configuration based on all HostPermitListPolicy entries
        grouped_proxy_rules = _get_egress_proxy_dns_port_rules(
            all_host_permit_list_policies
        )
        for i, proxy_rules in enumerate(grouped_proxy_rules):
            egress_proxy_name = f"{SUFFIX_EGRESS_PROXY_NAME}-{i}"

            # add new network for each proxy where it can be reached
            _add_egress_proxy_network(service_spec, egress_proxy_name)

            egress_proxy_config = _get_egress_proxy_service_config(
                egress_proxy_rules=proxy_rules,
                network_with_internet=_DEFAULT_USER_SERVICES_NETWORK_WITH_INTERNET_NAME,
                egress_proxy_settings=egress_proxy_settings,
                egress_proxy_name=egress_proxy_name,
            )
            logger.debug(
                "EGRESS PROXY '%s' CONFIG:\n%s",
                egress_proxy_name,
                yaml.safe_dump(egress_proxy_config),
            )
            # adds a new service configuration here
            service_spec["services"][egress_proxy_name] = egress_proxy_config

            # extract dependency between container_name and egress_proxy_name
            for proxy_rule in proxy_rules:
                container_name = hostname_port_to_container_name[
                    (proxy_rule[0].hostname, proxy_rule[1])
                ]
                if container_name not in container_name_to_proxies_names:
                    container_name_to_proxies_names[container_name] = set()
                container_name_to_proxies_names[container_name].add(egress_proxy_name)

        for container_name, proxy_names in container_name_to_proxies_names.items():
            # attach `depends_on` rules to all container
            service_spec["services"][container_name]["depends_on"] = list(proxy_names)
            # attach proxy network to allow
            service_networks = service_spec["services"][container_name].get(
                "networks", {}
            )
            for proxy_name in proxy_names:
                service_networks[_get_egress_proxy_network_name(proxy_name)] = None
                service_spec["services"][container_name]["networks"] = service_networks
