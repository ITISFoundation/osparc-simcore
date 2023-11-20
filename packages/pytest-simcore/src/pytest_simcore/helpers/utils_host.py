import socket


def get_localhost_ip(default="127.0.0.1") -> str:
    """Return the IP address for localhost"""
    local_ip = default
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(("10.255.255.255", 1))
        local_ip = s.getsockname()[0]
    finally:
        s.close()
    return f"{local_ip}"
