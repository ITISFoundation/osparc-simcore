from pathlib import Path


def get_system_extra_hosts_raw(extra_host_domain: str) -> list[str]:
    extra_hosts = []
    hosts_path = Path("/etc/hosts")
    if hosts_path.exists() and extra_host_domain != "undefined":
        with hosts_path.open() as hosts:
            extra_hosts = [
                line.strip().replace("\t", " ")
                for line in hosts
                if extra_host_domain in line
            ]

    return extra_hosts
