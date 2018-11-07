
import abc

from yarl import URL


class ServiceResolutionPolicy(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    async def get_image_name(self, service_identifier: str) -> str:
        """
            Idenfies a type of service
        """
        pass

    @abc.abstractmethod
    async def get_url(self, service_identifier: str) -> URL:
        pass


    # TODO: on_closed signal to notify sub-system that the service
    # has closed and can raise HTTPServiceAnavailable
