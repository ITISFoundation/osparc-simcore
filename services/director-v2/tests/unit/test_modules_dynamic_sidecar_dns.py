# pylint: disable=redefined-outer-name


import asyncio
from ipaddress import IPv4Address

import pytest
from fastapi import FastAPI
from simcore_service_director_v2.modules.dynamic_sidecar.dns import (
    SimpleDNSResolver,
    get_simple_dns_resolver,
    setup,
    shutdown,
)


@pytest.fixture
def app() -> FastAPI:
    return FastAPI()


@pytest.fixture
async def simple_dns_resolver(app: FastAPI) -> SimpleDNSResolver:
    await setup(app)
    yield get_simple_dns_resolver(app)
    await shutdown(app)


@pytest.mark.parametrize(
    "dns, resolver_address, resolver_port",
    [
        ("google.com", "1.1.1.1", 53),
        ("github.com", "8.8.8.8", 53),
    ],
)
async def test_dns_query_ok(
    simple_dns_resolver: SimpleDNSResolver,
    dns: str,
    resolver_address: str,
    resolver_port: int,
):
    ip_address = await simple_dns_resolver.dns_query(
        dns, resolver_address, resolver_port
    )
    assert type(ip_address) == IPv4Address


async def test_dns_query_cannot_resolve(simple_dns_resolver: SimpleDNSResolver):
    not_existing_dns = "dummy-domain-dns-that-is-missing.example.com"
    with pytest.raises(RuntimeError) as exec_info:
        await simple_dns_resolver.dns_query(not_existing_dns, "1.1.1.1", 53)
    assert (
        f"Could not resolve '{not_existing_dns}' with server 1.1.1.1:53."
        in f"{exec_info}"
    )


async def test_parallel_dns_queries(simple_dns_resolver: SimpleDNSResolver):
    await asyncio.gather(
        *[simple_dns_resolver.dns_query("google.com", "1.1.1.1", 53) for _ in range(10)]
    )
