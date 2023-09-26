# pylint: disable=redefined-outer-name

from collections import deque
from pathlib import Path
from typing import Any, Final

import pytest
import yaml
from models_library.basic_types import PortInt
from models_library.service_settings_nat_rule import (
    DEFAULT_DNS_SERVER_ADDRESS,
    DEFAULT_DNS_SERVER_PORT,
    NATRule,
    _PortRange,
)
from ordered_set import OrderedSet
from pydantic import NonNegativeInt
from simcore_service_director_v2.modules.dynamic_sidecar.docker_compose_egress_config import (
    _get_egress_proxy_dns_port_rules,
    _get_envoy_config,
    _HostData,
    _ProxyRule,
)

# UTILS

N: Final[NonNegativeInt] = 100


def _pr(hostname: str, port: PortInt) -> _ProxyRule:
    # short name factory for _ProxyRule with default DNS
    return (
        _HostData(
            hostname=hostname,
            dns_resolver_address=DEFAULT_DNS_SERVER_ADDRESS,
            dns_resolver_port=DEFAULT_DNS_SERVER_PORT,
        ),
        port,
    )


def _u(list_of_ordered_sets: list[OrderedSet[_ProxyRule]]) -> OrderedSet[_ProxyRule]:
    # apply set union to list of sets
    result_set: OrderedSet[_ProxyRule] = OrderedSet()
    for ordered_set in list_of_ordered_sets:
        result_set |= ordered_set
    return result_set


# FIXTURES


@pytest.fixture
def envoy_conf(mocks_dir: Path) -> dict[str, Any]:
    envoy_conf = mocks_dir / "working_envoy_proxy_config.yaml"
    assert envoy_conf.exists()
    return yaml.safe_load(envoy_conf.read_text())


# TESTS


@pytest.mark.parametrize(
    "host_permit_list_policies, expected_grouped_proxy_rules",
    [
        pytest.param(
            [NATRule(hostname="", tcp_ports=[1])],
            [OrderedSet({_pr("", 1)})],
            id="one_port",
        ),
        pytest.param(
            [NATRule(hostname="abc", tcp_ports=[1, _PortRange(lower=1, upper=N)])],
            [
                _u(OrderedSet({_pr("abc", x)}) for x in range(1, N + 1)),
            ],
            id="mix_port_range",
        ),
        pytest.param(
            [
                NATRule(hostname="abc", tcp_ports=[_PortRange(lower=1, upper=N), 999]),
                NATRule(hostname="xyz", tcp_ports=[_PortRange(lower=1, upper=N), 999]),
            ],
            [
                _u(OrderedSet({_pr("abc", x)}) for x in range(1, N + 1))
                | OrderedSet({_pr("abc", 999)}),
                _u(OrderedSet({_pr("xyz", x)}) for x in range(1, N + 1))
                | OrderedSet({_pr("xyz", 999)}),
            ],
            id="mix_same_ports_on_two_separate_hosts",
        ),
        pytest.param(
            [NATRule(hostname=f"abc{x}", tcp_ports=[80, 443]) for x in range(2)],
            [
                OrderedSet({_pr(f"abc{x}", 80)}) | OrderedSet({_pr(f"abc{x}", 443)})
                for x in range(2)
            ],
            id="mix_lots_of_http_permit_listing",
        ),
    ],
)
def test_get_egress_proxy_dns_port_rules(
    host_permit_list_policies: list[NATRule],
    expected_grouped_proxy_rules: deque[set[tuple[str, PortInt]]],
):
    grouped_proxy_rules = _get_egress_proxy_dns_port_rules(host_permit_list_policies)

    # sorting by hostname in set
    sorted_grouped_proxy_rules = sorted(
        grouped_proxy_rules, key=lambda x: iter(x).__next__()[0]
    )
    sorted_expected_grouped_proxy_rules = sorted(
        expected_grouped_proxy_rules, key=lambda x: iter(x).__next__()[0]
    )
    assert sorted_grouped_proxy_rules == sorted_expected_grouped_proxy_rules


def test_get_envoy_config(envoy_conf: dict[str, Any]):
    proxy_rules: OrderedSet[_ProxyRule] = OrderedSet()

    proxy_rules.add(
        (
            _HostData(
                hostname="d1.d2.com",
                dns_resolver_address="1.1.1.1",
                dns_resolver_port=53,
            ),
            1267,
        )
    )
    proxy_rules.add(
        (
            _HostData(
                hostname="d1.d2.com",
                dns_resolver_address="1.1.1.1",
                dns_resolver_port=53,
            ),
            6589,
        )
    )
    proxy_rules.add(
        (
            _HostData(
                hostname="github.com",
                dns_resolver_address="8.8.8.8",
                dns_resolver_port=53,
            ),
            443,
        )
    )

    envoy_proxy_config = _get_envoy_config(proxy_rules)

    assert envoy_proxy_config == envoy_conf
