# coding: utf-8

from __future__ import absolute_import
from datetime import date, datetime  # noqa: F401

from typing import List, Dict  # noqa: F401

from .base_model_ import Model
from .inline_response200_data import InlineResponse200Data  # noqa: F401,E501
from .. import util


class InlineResponse200(Model):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.
    """

    def __init__(self, data: InlineResponse200Data=None, error: object=None):  # noqa: E501
        """InlineResponse200 - a model defined in OpenAPI

        :param data: The data of this InlineResponse200.  # noqa: E501
        :type data: InlineResponse200Data
        :param error: The error of this InlineResponse200.  # noqa: E501
        :type error: object
        """
        self.openapi_types = {
            'data': InlineResponse200Data,
            'error': object
        }

        self.attribute_map = {
            'data': 'data',
            'error': 'error'
        }

        self._data = data
        self._error = error

    @classmethod
    def from_dict(cls, dikt) -> 'InlineResponse200':
        """Returns the dict as a model

        :param dikt: A dict.
        :type: dict
        :return: The inline_response_200 of this InlineResponse200.  # noqa: E501
        :rtype: InlineResponse200
        """
        return util.deserialize_model(dikt, cls)

    @property
    def data(self) -> InlineResponse200Data:
        """Gets the data of this InlineResponse200.


        :return: The data of this InlineResponse200.
        :rtype: InlineResponse200Data
        """
        return self._data

    @data.setter
    def data(self, data: InlineResponse200Data):
        """Sets the data of this InlineResponse200.


        :param data: The data of this InlineResponse200.
        :type data: InlineResponse200Data
        """

        self._data = data

    @property
    def error(self) -> object:
        """Gets the error of this InlineResponse200.


        :return: The error of this InlineResponse200.
        :rtype: object
        """
        return self._error

    @error.setter
    def error(self, error: object):
        """Sets the error of this InlineResponse200.


        :param error: The error of this InlineResponse200.
        :type error: object
        """

        self._error = error
