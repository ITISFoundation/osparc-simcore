from pathlib import Path
from subprocess import CompletedProcess, run

from typing import Optional

DESTINATION = "dst"
SOURCE = "src"

CONFIG = """
[{destination}]
type = s3
provider = AWS
access_key_id = {aws_access_key}
secret_access_key = {aws_secret_key}
region = us-east-1
acl = private

[{source}]
type = s3
provider = Minio
access_key_id = {minio_access_key}
secret_access_key = {minio_secret_key}
endpoint = {minio_endpoint}
region = us-east-1
acl = private
"""


def assemble_config_file(
    aws_access_key: str,
    aws_secret_key: str,
    minio_access_key: str,
    minio_secret_key: str,
    minio_endpoint: Optional[str],
) -> Path:
    # NOTE: Since rclone requires slightly different configuration based on the
    # S3 provider, below assumptions are made:
    # - source: MINIO
    # - destination: AWS S3
    # The above CONFIG will require changing if this changes

    # minio endpoint must be provided
    assert minio_endpoint is not None  # nosec

    config_content = CONFIG.format(
        aws_access_key=aws_access_key,
        aws_secret_key=aws_secret_key,
        minio_access_key=minio_access_key,
        minio_secret_key=minio_secret_key,
        minio_endpoint=minio_endpoint,
        destination=DESTINATION,
        source=SOURCE,
    )

    conf_path = Path("/tmp/rclone_config.ini")  # nosec
    conf_path.write_text(config_content)
    return conf_path


def sync_file(
    config_path: Path, s3_object: str, source_bucket: str, destination_bucket: str
) -> None:
    source_path = Path(source_bucket) / s3_object
    destination_path = Path(destination_bucket) / s3_object
    file_name = destination_path.name

    # rclone only acts upon directories, so to target a specific file
    # it is required to add it as an include rule. Example of command below:
    #    rclone --config /tmp/rclone_config.ini sync \
    #       'minio:production-simcore/38a2e328-4c5c-11ec-854c-02420a0b01d2/04db21ce-3c52-48ca-9a2a-c239a1d84826' \
    #       's3:production-simcore/38a2e328-4c5c-11ec-854c-02420a0b01d2/04db21ce-3c52-48ca-9a2a-c239a1d84826' \
    #       -P \
    #       --include 'Readout_hummel_data_2022-02-18 03_54_06.807444.zip'
    r_clone_command = [
        "rclone",
        "--config",
        config_path,
        "sync",
        f"{SOURCE}:{source_path.parent}",
        f"{DESTINATION}:{destination_path.parent}",
        "-P",
        "--include",
        f"{file_name}",
    ]
    print(r_clone_command)

    result: CompletedProcess = run(r_clone_command, capture_output=True)
    print(result.stdout.decode())
    result.check_returncode()
