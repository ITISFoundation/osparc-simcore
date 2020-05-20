from pathlib import Path
from typing import List


def get_system_extra_hosts_raw(extra_host_domain: str) -> List[str]:
    extra_hosts = []
    hosts_path = Path("/etc/hosts")
    if hosts_path.exists() and extra_host_domain != "undefined":
        with hosts_path.open() as hosts:
            for line in hosts:
                if extra_host_domain in line:
                    extra_hosts.append(line.strip().replace("\t", " "))
    return extra_hosts
