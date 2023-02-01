import logging
from ipaddress import IPv4Address

from async_dns.core import Address, types
from async_dns.request import clean
from async_dns.resolver import DNSClient
from fastapi import FastAPI
from models_library.basic_types import PortInt
from pydantic import NonNegativeFloat, parse_obj_as

logger = logging.getLogger(__name__)


class SimpleDNSResolver:
    def __init__(self, timeout: NonNegativeFloat = 5.0) -> None:
        self.timeout = timeout

    async def dns_query(
        self,
        dns: str,
        resolver_address: str,
        resolver_port: PortInt,
    ) -> IPv4Address:
        """
        Simple DNS query, that searches for the domain name in the first level.
        It does not use any caching.
        """

        logger.error(  # TODO:downgrade to debug
            "dns=%s, resolver_address=%s, resolver_port=%s",
            dns,
            resolver_address,
            resolver_port,
        )

        query_reply = await DNSClient(timeout=self.timeout).query(
            dns,
            types.A,
            Address.parse(f"{resolver_address}:{resolver_port}"),
        )
        if len(query_reply.an) != 1:
            raise RuntimeError(
                f"Could not resolve '{dns}' with server "
                f"{resolver_address}:{resolver_port}. DNS query reply: {query_reply}"
            )

        str_ipv4 = query_reply.an[0].data.data

        return parse_obj_as(IPv4Address, str_ipv4)

    def shutdown(self):
        clean()


async def setup(app: FastAPI):
    app.state.simple_dns_resolver = SimpleDNSResolver()


async def shutdown(app: FastAPI):
    resolver: SimpleDNSResolver = app.state.simple_dns_resolver
    resolver.shutdown()


def get_simple_dns_resolver(app: FastAPI) -> SimpleDNSResolver:
    return app.state.simple_dns_resolver
