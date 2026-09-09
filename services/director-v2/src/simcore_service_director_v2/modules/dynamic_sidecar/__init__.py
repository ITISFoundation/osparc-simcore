"""
Helpful conventions in method names:
- `user_services` = the container(s) used to provide the service in the GUI
- `sidecar`, `proxy` = self referenced
- `pod` = sidecar,proxy+user_services
"""

from .module_setup import configure_dynamic_sidecar

__all__: tuple[str, ...] = ("configure_dynamic_sidecar",)
