"""
Helpful conventions in method names:
- `user_services` = the container(s) used to provide the service in the GUI
- `sidecar`, `proxy` = self referenced
- `pod` = sidecar,proxy+user_services
"""

from .module_setup import setup
