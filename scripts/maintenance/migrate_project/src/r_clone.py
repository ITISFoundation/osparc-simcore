from pathlib import Path
from subprocess import CompletedProcess, run

from settings_library.r_clone import S3Provider
from tenacity import retry
from tenacity.stop import stop_after_attempt

DESTINATION = "dst"
SOURCE = "src"

CONFIG = """
[{destination}]
type = s3
provider = {destination_provider}
access_key_id = {destination_access_key}
secret_access_key = {destination_secret_key}
endpoint = {destination_endpoint}
region = us-east-1
acl = private

[{source}]
type = s3
provider = {source_provider}
access_key_id = {source_access_key}
secret_access_key = {source_secret_key}
endpoint = {source_endpoint}
region = us-east-1
acl = private
"""


def assemble_config_file(
    source_access_key: str,
    source_secret_key: str,
    source_endpoint: str,
    source_provider: S3Provider,
    destination_access_key: str,
    destination_secret_key: str,
    destination_endpoint: str = "https://s3.amazonaws.com",
    destination_provider: S3Provider = S3Provider.AWS,
) -> Path:

    config_content = CONFIG.format(
        source_access_key=source_access_key,
        source_secret_key=source_secret_key,
        source_endpoint=source_endpoint,
        source_provider=source_provider,
        destination_access_key=destination_access_key,
        destination_secret_key=destination_secret_key,
        destination_endpoint=destination_endpoint,
        destination_provider=destination_provider,
        destination=DESTINATION,
        source=SOURCE,
    )

    conf_path = Path("/tmp/rclone_config.ini")  # nosec
    conf_path.write_text(config_content)
    return conf_path


@retry(stop=stop_after_attempt(3))
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
        "--low-level-retries",
        "3",
        "--retries",
        "3",
        "--transfers",
        "1",
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
