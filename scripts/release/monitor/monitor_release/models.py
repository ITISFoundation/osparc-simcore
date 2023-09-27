from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Deployment(str, Enum):
    master = "master"
    aws_staging = "aws-staging"
    dalco_staging = "dalco-staging"
    aws_production = "aws-production"
    dalco_production = "dalco-production"
    tip_production = "tip-production"


class RunningSidecar(BaseModel):
    name: str
    created_at: datetime
    user_id: str
    project_id: str
    service_key: str
    service_version: str
