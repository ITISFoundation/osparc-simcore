# coding: utf-8

from datetime import date, datetime

from typing import List, Dict, Type

from .base_model_ import Model
from .. import util


class InlineResponse2002DataContainerSpec(Model):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.
    """

    def __init__(self, command: List[str]=None):
        """InlineResponse2002DataContainerSpec - a model defined in OpenAPI

        :param command: The command of this InlineResponse2002DataContainerSpec.
        """
        self.openapi_types = {
            'command': List[str]
        }

        self.attribute_map = {
            'command': 'command'
        }

        self._command = command

    @classmethod
    def from_dict(cls, dikt: dict) -> 'InlineResponse2002DataContainerSpec':
        """Returns the dict as a model

        :param dikt: A dict.
        :return: The inline_response_200_2_data_container_spec of this InlineResponse2002DataContainerSpec.
        """
        return util.deserialize_model(dikt, cls)

    @property
    def command(self):
        """Gets the command of this InlineResponse2002DataContainerSpec.


        :return: The command of this InlineResponse2002DataContainerSpec.
        :rtype: List[str]
        """
        return self._command

    @command.setter
    def command(self, command):
        """Sets the command of this InlineResponse2002DataContainerSpec.


        :param command: The command of this InlineResponse2002DataContainerSpec.
        :type command: List[str]
        """

        self._command = command
