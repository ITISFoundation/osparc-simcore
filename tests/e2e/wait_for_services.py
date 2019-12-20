import docker
from typing import Dict
from pathlib import Path
from tenacity import retry

def core_docker_compose_file() -> Path:
    pass

def core_services() -> Dict[str]:
    pass

@retry()
def wait_for_services() -> bool:
    pass

if __name__ == "__main__":
    # get retry parameters
    # wait for the services
    
    pass