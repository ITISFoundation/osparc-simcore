from dataclasses import dataclass

from fastapi import FastAPI


@dataclass
class OSparcGateway:
    ...


async def _analyze_available_gateways(app: FastAPI) -> list[OSparcGateway]:
    return []


async def _remove_unused_gateways(app: FastAPI, gateways: list[OSparcGateway]) -> None:
    ...


async def check_clusters(app: FastAPI) -> None:
    gateways = await _analyze_available_gateways(app)
    await _remove_unused_gateways(app, gateways)
