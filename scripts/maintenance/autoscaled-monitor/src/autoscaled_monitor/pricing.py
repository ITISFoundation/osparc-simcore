"""AWS EC2 / EBS on-demand pricing lookups via the AWS Pricing API.

Region "location" names (as used by the AWS Price List) are resolved through a static mapping —
this is well-known, essentially immutable AWS data, so no extra AWS API call/permission is needed
just to translate a region code into its Price List location name.

Results are cached with aiocache (per-process, in-memory) to avoid looking up the pricing of the
same EC2 instance type / EBS volume type / region more than once.
"""

import datetime
import json
import os
from dataclasses import dataclass, field
from typing import Final

import boto3
import rich
from aiocache import cached
from mypy_boto3_ec2.service_resource import Instance

from .utils import to_async

# NOTE: the AWS Pricing API is only served from the us-east-1 (or ap-south-1) endpoint,
# regardless of which region the priced resources actually live in.
_PRICING_API_REGION: Final[str] = "us-east-1"

# average number of hours in a month, used to turn an hourly price into a monthly estimate
_HOURS_PER_MONTH: Final[float] = 24 * 30.44

# maps a region code to the "location" attribute used by the AWS Price List (static AWS data)
_REGION_TO_LOCATION: Final[dict[str, str]] = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "af-south-1": "Africa (Cape Town)",
    "ap-east-1": "Asia Pacific (Hong Kong)",
    "ap-south-1": "Asia Pacific (Mumbai)",
    "ap-south-2": "Asia Pacific (Hyderabad)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
    "ap-northeast-2": "Asia Pacific (Seoul)",
    "ap-northeast-3": "Asia Pacific (Osaka)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-southeast-3": "Asia Pacific (Jakarta)",
    "ap-southeast-4": "Asia Pacific (Melbourne)",
    "ca-central-1": "Canada (Central)",
    "ca-west-1": "Canada West (Calgary)",
    "eu-central-1": "EU (Frankfurt)",
    "eu-central-2": "EU (Zurich)",
    "eu-west-1": "EU (Ireland)",
    "eu-west-2": "EU (London)",
    "eu-west-3": "EU (Paris)",
    "eu-north-1": "EU (Stockholm)",
    "eu-south-1": "EU (Milan)",
    "eu-south-2": "EU (Spain)",
    "me-south-1": "Middle East (Bahrain)",
    "me-central-1": "Middle East (UAE)",
    "sa-east-1": "South America (Sao Paulo)",
    "il-central-1": "Israel (Tel Aviv)",
}


@dataclass(frozen=True, slots=True, kw_only=True)
class CostBreakdown:
    lines: list[str] = field(default_factory=list)
    hourly_usd: float | None = None
    accrued_usd: float | None = None


# NOTE: avoids spamming the console with the same AWS error on every single instance/volume
_warned_errors: set[str] = set()


def _warn_once(context: str, exc: Exception) -> None:
    key = f"{context}:{type(exc).__name__}"
    if key in _warned_errors:
        return
    _warned_errors.add(key)
    rich.print(f"[yellow]Warning: {context} failed ({type(exc).__name__}: {exc}). Costs will show as n/a.[/yellow]")


def get_region_location(region_name: str) -> str | None:
    """Returns the AWS Price List "location" name for a region code (e.g. "US East (N. Virginia)"),
    or None if the region is unknown."""
    return _REGION_TO_LOCATION.get(region_name)


def _get_boto3_session(
    profile_name: str | None, aws_access_key_id: str | None, aws_secret_access_key: str | None
) -> boto3.Session:
    """Prefer an explicit AWS profile (e.g. via --use-profile, or a developer's own credentials with
    pricing/EBS read access) when given, then the AWS_PROFILE env var, since the autoscaling/
    clusters-keeper access keys are usually narrowly scoped to EC2 instance management and may lack
    pricing:GetProducts / ec2:DescribeVolumes permissions."""
    resolved_profile_name = profile_name or os.environ.get("AWS_PROFILE")
    if resolved_profile_name:
        return boto3.Session(profile_name=resolved_profile_name)
    return boto3.Session(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)


def _has_usable_credentials(
    profile_name: str | None, aws_access_key_id: str | None, aws_secret_access_key: str | None
) -> bool:
    return bool(profile_name or os.environ.get("AWS_PROFILE")) or bool(aws_access_key_id and aws_secret_access_key)


def _extract_on_demand_usd_price(price_list_item: str) -> float | None:
    data = json.loads(price_list_item)
    for term in data.get("terms", {}).get("OnDemand", {}).values():
        for price_dimension in term.get("priceDimensions", {}).values():
            usd = price_dimension.get("pricePerUnit", {}).get("USD")
            if usd:
                return float(usd)
    return None


@to_async
def _fetch_ec2_hourly_usd_price(
    instance_type: str,
    location: str,
    profile_name: str | None,
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
) -> float | None:
    try:
        client = _get_boto3_session(profile_name, aws_access_key_id, aws_secret_access_key).client(
            "pricing", region_name=_PRICING_API_REGION
        )
        response = client.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
            ],
            MaxResults=1,
        )
        for price_list_item in response.get("PriceList", []):
            if (price := _extract_on_demand_usd_price(price_list_item)) is not None:
                return price
        return None
    except Exception as exc:  # pylint: disable=broad-exception-caught  # nosec
        _warn_once("fetching EC2 pricing (pricing:GetProducts)", exc)
        return None


@cached()
async def get_ec2_hourly_usd_price(
    instance_type: str,
    region_name: str,
    profile_name: str | None,
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
) -> float | None:
    """Returns the AWS on-demand hourly USD price for a Linux EC2 instance type, or None if unavailable."""
    if not _has_usable_credentials(profile_name, aws_access_key_id, aws_secret_access_key):
        return None
    location = get_region_location(region_name)
    if location is None:
        return None
    return await _fetch_ec2_hourly_usd_price(
        instance_type, location, profile_name, aws_access_key_id, aws_secret_access_key
    )


@to_async
def _fetch_ebs_gb_month_usd_price(
    volume_type: str,
    location: str,
    profile_name: str | None,
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
) -> float | None:
    try:
        client = _get_boto3_session(profile_name, aws_access_key_id, aws_secret_access_key).client(
            "pricing", region_name=_PRICING_API_REGION
        )
        response = client.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Storage"},
                {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                {"Type": "TERM_MATCH", "Field": "volumeApiName", "Value": volume_type},
            ],
            MaxResults=1,
        )
        for price_list_item in response.get("PriceList", []):
            if (price := _extract_on_demand_usd_price(price_list_item)) is not None:
                return price
        return None
    except Exception as exc:  # pylint: disable=broad-exception-caught  # nosec
        _warn_once("fetching EBS pricing (pricing:GetProducts)", exc)
        return None


@cached()
async def get_ebs_gb_month_usd_price(
    volume_type: str,
    region_name: str,
    profile_name: str | None,
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
) -> float | None:
    """Returns the AWS on-demand USD price per GB-month of EBS storage, or None if unavailable."""
    if not _has_usable_credentials(profile_name, aws_access_key_id, aws_secret_access_key):
        return None
    location = get_region_location(region_name)
    if location is None:
        return None
    return await _fetch_ebs_gb_month_usd_price(
        volume_type, location, profile_name, aws_access_key_id, aws_secret_access_key
    )


@to_async
def _fetch_instance_ebs_volumes(
    instance_id: str,
    region_name: str,
    profile_name: str | None,
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
) -> list[tuple[str, int]]:
    # NOTE: uses the resolved session (--use-profile, AWS_PROFILE, or explicit keys) rather than the
    # EC2 resource's own (possibly narrowly-scoped) client, so a profile can also be used for ec2:DescribeVolumes.
    try:
        client = _get_boto3_session(profile_name, aws_access_key_id, aws_secret_access_key).client(
            "ec2", region_name=region_name
        )
        response = client.describe_volumes(
            Filters=[{"Name": "attachment.instance-id", "Values": [instance_id]}],
        )
        return [(volume["VolumeType"], volume["Size"]) for volume in response.get("Volumes", [])]
    except Exception as exc:  # pylint: disable=broad-exception-caught  # nosec
        _warn_once("listing EBS volumes (ec2:DescribeVolumes)", exc)
        return []


async def get_cost_info(
    ec2_instance: Instance,
    region_name: str,
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
    *,
    profile_name: str | None = None,
    indent: str = "",
) -> CostBreakdown:
    """Returns the estimated EC2/EBS hourly rates and the accrued cost since the instance launched.

    Unavailable values (e.g. missing pricing:GetProducts / ec2:DescribeVolumes permissions) are
    omitted rather than shown as "n/a"; a single hint line pointing at --use-profile is added instead.
    """
    hourly_price = await get_ec2_hourly_usd_price(
        ec2_instance.instance_type, region_name, profile_name, aws_access_key_id, aws_secret_access_key
    )
    lines: list[str] = []
    if hourly_price is not None:
        lines.append(f"{indent}EC2 cost: ${hourly_price:.4f}/h")

    volumes = await _fetch_instance_ebs_volumes(
        ec2_instance.instance_id, region_name, profile_name, aws_access_key_id, aws_secret_access_key
    )
    ebs_hourly_price: float | None = 0.0
    if volumes:
        ebs_gb_total = sum(size for _, size in volumes)
        for volume_type, size in volumes:
            gb_month_price = await get_ebs_gb_month_usd_price(
                volume_type, region_name, profile_name, aws_access_key_id, aws_secret_access_key
            )
            if gb_month_price is None:
                ebs_hourly_price = None
                break
            ebs_hourly_price += (gb_month_price / _HOURS_PER_MONTH) * size
        if ebs_hourly_price is not None:
            lines.append(f"{indent}EBS cost: ${ebs_hourly_price:.4f}/h ({ebs_gb_total} GiB)")

    total_hourly_price = (
        hourly_price + ebs_hourly_price if hourly_price is not None and ebs_hourly_price is not None else None
    )
    accrued_price: float | None = None
    if total_hourly_price is not None:
        elapsed_hours = max(
            (datetime.datetime.now(datetime.UTC) - ec2_instance.launch_time).total_seconds() / 3600, 0.0
        )
        accrued_price = total_hourly_price * elapsed_hours
        lines.append(f"{indent}Total cost: ${accrued_price:.2f} so far")
    elif profile_name:
        lines.append(
            f"{indent}[dim]Costs unavailable via profile '{profile_name}' "
            "\u2014 check its pricing:GetProducts/ec2:DescribeVolumes permissions[/dim]"
        )
    else:
        lines.append(f"{indent}[dim]Costs unavailable \u2014 try --use-profile <aws-profile>[/dim]")

    return CostBreakdown(lines=lines, hourly_usd=total_hourly_price, accrued_usd=accrued_price)
