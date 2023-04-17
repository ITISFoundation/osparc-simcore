# coding: utf-8

from datetime import date, datetime

from typing import List, Dict, Type

from .base_model_ import Model
from .inline_response2002_data_container_spec import InlineResponse2002DataContainerSpec
from .inline_response2002_data_node_requirements import InlineResponse2002DataNodeRequirements
from .inline_response2002_data_service_build_details import InlineResponse2002DataServiceBuildDetails
from .. import util


class InlineResponse2002Data(Model):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.
    """

    def __init__(self, node_requirements: InlineResponse2002DataNodeRequirements=None, service_build_details: InlineResponse2002DataServiceBuildDetails=None, container_spec: InlineResponse2002DataContainerSpec=None):
        """InlineResponse2002Data - a model defined in OpenAPI

        :param node_requirements: The node_requirements of this InlineResponse2002Data.
        :param service_build_details: The service_build_details of this InlineResponse2002Data.
        :param container_spec: The container_spec of this InlineResponse2002Data.
        """
        self.openapi_types = {
            'node_requirements': InlineResponse2002DataNodeRequirements,
            'service_build_details': InlineResponse2002DataServiceBuildDetails,
            'container_spec': InlineResponse2002DataContainerSpec
        }

        self.attribute_map = {
            'node_requirements': 'node_requirements',
            'service_build_details': 'service_build_details',
            'container_spec': 'container_spec'
        }

        self._node_requirements = node_requirements
        self._service_build_details = service_build_details
        self._container_spec = container_spec

    @classmethod
    def from_dict(cls, dikt: dict) -> 'InlineResponse2002Data':
        """Returns the dict as a model

        :param dikt: A dict.
        :return: The inline_response_200_2_data of this InlineResponse2002Data.
        """
        return util.deserialize_model(dikt, cls)

    @property
    def node_requirements(self):
        """Gets the node_requirements of this InlineResponse2002Data.


        :return: The node_requirements of this InlineResponse2002Data.
        :rtype: InlineResponse2002DataNodeRequirements
        """
        return self._node_requirements

    @node_requirements.setter
    def node_requirements(self, node_requirements):
        """Sets the node_requirements of this InlineResponse2002Data.


        :param node_requirements: The node_requirements of this InlineResponse2002Data.
        :type node_requirements: InlineResponse2002DataNodeRequirements
        """
        if node_requirements is None:
            raise ValueError("Invalid value for `node_requirements`, must not be `None`")

        self._node_requirements = node_requirements

    @property
    def service_build_details(self):
        """Gets the service_build_details of this InlineResponse2002Data.


        :return: The service_build_details of this InlineResponse2002Data.
        :rtype: InlineResponse2002DataServiceBuildDetails
        """
        return self._service_build_details

    @service_build_details.setter
    def service_build_details(self, service_build_details):
        """Sets the service_build_details of this InlineResponse2002Data.


        :param service_build_details: The service_build_details of this InlineResponse2002Data.
        :type service_build_details: InlineResponse2002DataServiceBuildDetails
        """

        self._service_build_details = service_build_details

    @property
    def container_spec(self):
        """Gets the container_spec of this InlineResponse2002Data.


        :return: The container_spec of this InlineResponse2002Data.
        :rtype: InlineResponse2002DataContainerSpec
        """
        return self._container_spec

    @container_spec.setter
    def container_spec(self, container_spec):
        """Sets the container_spec of this InlineResponse2002Data.


        :param container_spec: The container_spec of this InlineResponse2002Data.
        :type container_spec: InlineResponse2002DataContainerSpec
        """

        self._container_spec = container_spec
