from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from temporalio.client import Client

from ._registry import WorkflowRegistry

if TYPE_CHECKING:
    from ._engine import WorkflowEngine


def get_temporalio_client(app: FastAPI) -> Client:
    client: Client = app.state.temporalio_client
    return client


def get_workflow_registry(app: FastAPI) -> WorkflowRegistry:
    registry: WorkflowRegistry = app.state.workflow_registry
    return registry


def get_workflow_engine(app: FastAPI) -> WorkflowEngine:
    engine: WorkflowEngine = app.state.workflow_engine
    return engine
