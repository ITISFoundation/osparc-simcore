
import abc

from yarl import URL

from .settings import PROXY_MOUNTPOINT


class ServiceResolutionPolicy(metaclass=abc.ABCMeta):
    """ Implements an interface to identify and
        resolve the location of a dynamic backend service
    """
    base_mountpoint = PROXY_MOUNTPOINT

    @abc.abstractmethod
    async def get_image_name(self, service_identifier: str) -> str:
        """
            Identifies a type of service. This normally corresponds
            to the name of the docker image
        """
        pass

    @abc.abstractmethod
    async def find_url(self, service_identifier: str) -> URL:
        """
            Return the complete url (including the mountpoint) of
            the service in the backend

            This access should be accesible by the proxy server

            E.g. 'http://127.0.0.1:58873/x/ae1q8/'
        """
        pass

    # TODO: on_closed signal to notify sub-system that the service
    # has closed and can raise HTTPServiceAnavailable
