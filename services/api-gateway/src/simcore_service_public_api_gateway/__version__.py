""" Current version of the simcore_service_public_api_gateway application.

This project uses the Semantic Versioning scheme in conjunction with PEP 0440:

    <http://semver.org/>
    <https://www.python.org/dev/peps/pep-0440>


Major versions introduce significant changes to the API, and backwards
compatibility is not guaranteed.

Minor versions are for new features and other backwards-compatible changes to the API.

Patch versions are for bug fixes and internal code changes that do not affect the API.

Pre-release and development versions are denoted appending a hyphen, i.e. 0.1.0-dev

Build metadata (e.g. git commit id, build id, ...) can be appended with a plus, i.e. 0.1.0-dev+asd21ff

Package version is defined in the setup.py following the principle of single-sourcing (option 5):
<https://packaging.python.org/guides/single-sourcing-package-version/>

"""
import pkg_resources

__version__ = pkg_resources.get_distribution('simcore_service_public_api_gateway').version

major, minor, patch = __version__.split('.')

api_version = __version__
api_version_prefix: str = f"v{major}"
