from enum import Enum


class Deployment(str, Enum):
    master = "master"
    aws_staging = "aws-staging"
    dalco_staging = "dalco-staging"
    aws_production = "aws-production"
    dalco_production = "dalco-production"
    tip_production = "tip-production"
