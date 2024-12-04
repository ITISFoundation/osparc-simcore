from pathlib import Path

from pydantic import Field

from .base import BaseCustomSettings


class AwsEfsSettings(BaseCustomSettings):
    EFS_DNS_NAME: str = Field(
        description="AWS Elastic File System DNS name",
        examples=["fs-xxx.efs.us-east-1.amazonaws.com"],
    )
    EFS_PROJECT_SPECIFIC_DATA_DIRECTORY: str
    EFS_MOUNTED_PATH: Path = Field(
        description="This is the path where EFS is mounted to the EC2 machine",
    )


NFS_PROTOCOL = "4.1"
READ_SIZE = "1048576"
WRITE_SIZE = "1048576"
RECOVERY_MODE = "hard"
NFS_REQUEST_TIMEOUT = "600"
NUMBER_OF_RETRANSMISSIONS = "2"
PORT_MODE = "noresvport"

"""
`sudo mount -t nfs -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport`

Explanation:

nfsvers=4.1: Specifies the NFS protocol version to use; here, it is version 4.1, which supports improved security features and performance optimizations over earlier versions.

rsize=1048576 and wsize=1048576: Set the read and write buffer sizes in bytes, respectively. Here, both are set to 1,048,576 bytes (1 MB). Larger buffer sizes can improve performance over high-latency networks by allowing more data to be transferred with each read or write request.

hard: Specifies the recovery behavior of the NFS client. If the NFS server becomes unreachable, the NFS client will retry the request until the server becomes available again. The alternative is soft, where the NFS client gives up after a certain number of retries, potentially leading to data corruption or loss.

timeo=600: Sets the timeout value for NFS requests in deciseconds (tenths of a second). Here, 600 deciseconds means 60 seconds. This is how long the NFS client will wait for a response from the server before retrying or failing.

retrans=2: Sets the number of retransmissions for each NFS request if a response is not received before the timeout. Here, it will retry each request twice.

noresvport: Normally, NFS uses a reserved port (number below 1024) for communicating, which requires root privileges on the client side. noresvport allows using non-reserved ports, which can be helpful in environments where clients don't have root privileges.
"""
