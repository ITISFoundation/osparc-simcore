from pathlib import Path
from typing import Dict


def get_system_extra_hosts(extra_host_domain: str) -> Dict:
    extra_hosts = {}
    hosts_path = Path("/etc/hosts")
    if hosts_path.exists() and extra_host_domain != "undefined":        
        with hosts_path.open() as hosts:
            for line in hosts:
                if extra_host_domain in line:
                    host = line.split()[1]
                    ip = line.split()[0]
                    extra_hosts[host] = ip
    return extra_hosts
