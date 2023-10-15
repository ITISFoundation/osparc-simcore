from collections.abc import Generator
from typing import Any, ClassVar, Final

from pydantic import BaseModel, Extra, Field, parse_obj_as, validator

from .basic_types import PortInt
from .osparc_variable_identifier import OsparcVariableIdentifier, raise_if_unresolved

# Cloudflare DNS server address
DEFAULT_DNS_SERVER_ADDRESS: Final[str] = "1.1.1.1"  # NOSONAR
DEFAULT_DNS_SERVER_PORT: Final[PortInt] = parse_obj_as(PortInt, 53)


class _PortRange(BaseModel):
    """`lower` and `upper` are included"""

    lower: PortInt | OsparcVariableIdentifier
    upper: PortInt | OsparcVariableIdentifier

    @validator("upper")
    @classmethod
    def lower_less_than_upper(cls, v, values) -> PortInt:
        if isinstance(v, OsparcVariableIdentifier):
            return v  # type: ignore # bypass validation if unresolved

        upper = v
        lower: PortInt | OsparcVariableIdentifier | None = values.get("lower")

        if lower and isinstance(lower, OsparcVariableIdentifier):
            return v  # type: ignore # bypass validation if unresolved

        if lower is None or lower >= upper:
            msg = f"Condition not satisfied: lower={lower!r} < upper={upper!r}"
            raise ValueError(msg)
        return PortInt(v)

    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True


class DNSResolver(BaseModel):
    address: OsparcVariableIdentifier | str = Field(
        ..., description="this is not an url address is derived from IP address"
    )
    port: PortInt | OsparcVariableIdentifier

    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True
        extra = Extra.allow
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"address": "1.1.1.1", "port": 53},  # NOSONAR
                {"address": "ns1.example.com", "port": 53},
            ]
        }


class NATRule(BaseModel):
    """Content of "simcore.service.containers-allowed-outgoing-permit-list" label"""

    hostname: OsparcVariableIdentifier | str
    tcp_ports: list[PortInt | OsparcVariableIdentifier | _PortRange]
    dns_resolver: DNSResolver = Field(
        default_factory=lambda: DNSResolver(
            address=DEFAULT_DNS_SERVER_ADDRESS, port=DEFAULT_DNS_SERVER_PORT
        ),
        description="specify a DNS resolver address and port",
    )

    def iter_tcp_ports(self) -> Generator[PortInt, None, None]:
        for port in self.tcp_ports:
            if isinstance(port, _PortRange):
                yield from (
                    PortInt(i)
                    for i in range(
                        raise_if_unresolved(port.lower),
                        raise_if_unresolved(port.upper) + 1,
                    )
                )
            else:
                yield raise_if_unresolved(port)

    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True
