
import abc

from yarl import URL

from .settings import PROXY_MOUNTPOINT

class ServiceResolutionPolicy(metaclass=abc.ABCMeta):
    """
        Idenfitication of a running dyb service
        Retrieves information about it
    """
    @property
    def service_basepath(self):
        """
            All external services should be mounted here
        """
        # This is how we communicate to the external user
        # where reverse_proxy is listening
        return PROXY_MOUNTPOINT



    @abc.abstractmethod
    async def get_image_name(self, service_identifier: str) -> str:
        """
            Idenfies a type of service
        """
        pass

    @abc.abstractmethod
    async def get_url(self, service_identifier: str) -> URL:
        """
            Full service end-point url

            Ex. 'http://127.0.0.1:58873/x/ae1q8/'
        """
        pass


    # TODO: on_closed signal to notify sub-system that the service
    # has closed and can raise HTTPServiceAnavailable
