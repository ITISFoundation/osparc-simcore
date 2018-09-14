# coding: utf-8

from __future__ import absolute_import
from datetime import date, datetime  # noqa: F401

from typing import List, Dict  # noqa: F401

from .base_model_ import Model
from .nodemetav0_authors import Nodemetav0Authors  # noqa: F401,E501
import re  # noqa: F401,E501
from .. import util


class NodeMetaV0(Model):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.
    """

    def __init__(self, key: str=None, version: str=None, type: str=None, name: str=None, description: str=None, authors: List[Nodemetav0Authors]=None, contact: str=None, inputs: object=None, outputs: object=None):  # noqa: E501
        """NodeMetaV0 - a model defined in OpenAPI

        :param key: The key of this NodeMetaV0.  # noqa: E501
        :type key: str
        :param version: The version of this NodeMetaV0.  # noqa: E501
        :type version: str
        :param type: The type of this NodeMetaV0.  # noqa: E501
        :type type: str
        :param name: The name of this NodeMetaV0.  # noqa: E501
        :type name: str
        :param description: The description of this NodeMetaV0.  # noqa: E501
        :type description: str
        :param authors: The authors of this NodeMetaV0.  # noqa: E501
        :type authors: List[Nodemetav0Authors]
        :param contact: The contact of this NodeMetaV0.  # noqa: E501
        :type contact: str
        :param inputs: The inputs of this NodeMetaV0.  # noqa: E501
        :type inputs: object
        :param outputs: The outputs of this NodeMetaV0.  # noqa: E501
        :type outputs: object
        """
        self.openapi_types = {
            'key': str,
            'version': str,
            'type': str,
            'name': str,
            'description': str,
            'authors': List[Nodemetav0Authors],
            'contact': str,
            'inputs': object,
            'outputs': object
        }

        self.attribute_map = {
            'key': 'key',
            'version': 'version',
            'type': 'type',
            'name': 'name',
            'description': 'description',
            'authors': 'authors',
            'contact': 'contact',
            'inputs': 'inputs',
            'outputs': 'outputs'
        }

        self._key = key
        self._version = version
        self._type = type
        self._name = name
        self._description = description
        self._authors = authors
        self._contact = contact
        self._inputs = inputs
        self._outputs = outputs

    @classmethod
    def from_dict(cls, dikt) -> 'NodeMetaV0':
        """Returns the dict as a model

        :param dikt: A dict.
        :type: dict
        :return: The node-meta-v0 of this NodeMetaV0.  # noqa: E501
        :rtype: NodeMetaV0
        """
        return util.deserialize_model(dikt, cls)

    @property
    def key(self) -> str:
        """Gets the key of this NodeMetaV0.

        distinctive name for the node based on the docker registry path  # noqa: E501

        :return: The key of this NodeMetaV0.
        :rtype: str
        """
        return self._key

    @key.setter
    def key(self, key: str):
        """Sets the key of this NodeMetaV0.

        distinctive name for the node based on the docker registry path  # noqa: E501

        :param key: The key of this NodeMetaV0.
        :type key: str
        """
        if key is None:
            raise ValueError("Invalid value for `key`, must not be `None`")  # noqa: E501
        if key is not None and not re.search('^(simcore)\/(services)\/(comp|dynamic)(\/[^\\s\/]+)+$', key):  # noqa: E501
            raise ValueError("Invalid value for `key`, must be a follow pattern or equal to `/^(simcore)\/(services)\/(comp|dynamic)(\/[^\\s\/]+)+$/`")  # noqa: E501

        self._key = key

    @property
    def version(self) -> str:
        """Gets the version of this NodeMetaV0.

        semantic version number  # noqa: E501

        :return: The version of this NodeMetaV0.
        :rtype: str
        """
        return self._version

    @version.setter
    def version(self, version: str):
        """Sets the version of this NodeMetaV0.

        semantic version number  # noqa: E501

        :param version: The version of this NodeMetaV0.
        :type version: str
        """
        if version is None:
            raise ValueError("Invalid value for `version`, must not be `None`")  # noqa: E501
        if version is not None and not re.search('^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$', version):  # noqa: E501
            raise ValueError("Invalid value for `version`, must be a follow pattern or equal to `/^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$/`")  # noqa: E501

        self._version = version

    @property
    def type(self) -> str:
        """Gets the type of this NodeMetaV0.

        service type  # noqa: E501

        :return: The type of this NodeMetaV0.
        :rtype: str
        """
        return self._type

    @type.setter
    def type(self, type: str):
        """Sets the type of this NodeMetaV0.

        service type  # noqa: E501

        :param type: The type of this NodeMetaV0.
        :type type: str
        """
        allowed_values = ["computational", "dynamic"]  # noqa: E501
        if type not in allowed_values:
            raise ValueError(
                "Invalid value for `type` ({0}), must be one of {1}"
                .format(type, allowed_values)
            )

        self._type = type

    @property
    def name(self) -> str:
        """Gets the name of this NodeMetaV0.

        short, human readable name for the node  # noqa: E501

        :return: The name of this NodeMetaV0.
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, name: str):
        """Sets the name of this NodeMetaV0.

        short, human readable name for the node  # noqa: E501

        :param name: The name of this NodeMetaV0.
        :type name: str
        """
        if name is None:
            raise ValueError("Invalid value for `name`, must not be `None`")  # noqa: E501

        self._name = name

    @property
    def description(self) -> str:
        """Gets the description of this NodeMetaV0.

        human readable description of the purpose of the node  # noqa: E501

        :return: The description of this NodeMetaV0.
        :rtype: str
        """
        return self._description

    @description.setter
    def description(self, description: str):
        """Sets the description of this NodeMetaV0.

        human readable description of the purpose of the node  # noqa: E501

        :param description: The description of this NodeMetaV0.
        :type description: str
        """
        if description is None:
            raise ValueError("Invalid value for `description`, must not be `None`")  # noqa: E501

        self._description = description

    @property
    def authors(self) -> List[Nodemetav0Authors]:
        """Gets the authors of this NodeMetaV0.


        :return: The authors of this NodeMetaV0.
        :rtype: List[Nodemetav0Authors]
        """
        return self._authors

    @authors.setter
    def authors(self, authors: List[Nodemetav0Authors]):
        """Sets the authors of this NodeMetaV0.


        :param authors: The authors of this NodeMetaV0.
        :type authors: List[Nodemetav0Authors]
        """
        if authors is None:
            raise ValueError("Invalid value for `authors`, must not be `None`")  # noqa: E501

        self._authors = authors

    @property
    def contact(self) -> str:
        """Gets the contact of this NodeMetaV0.

        email to correspond to the authors about the node  # noqa: E501

        :return: The contact of this NodeMetaV0.
        :rtype: str
        """
        return self._contact

    @contact.setter
    def contact(self, contact: str):
        """Sets the contact of this NodeMetaV0.

        email to correspond to the authors about the node  # noqa: E501

        :param contact: The contact of this NodeMetaV0.
        :type contact: str
        """
        if contact is None:
            raise ValueError("Invalid value for `contact`, must not be `None`")  # noqa: E501

        self._contact = contact

    @property
    def inputs(self) -> object:
        """Gets the inputs of this NodeMetaV0.

        definition of the inputs of this node  # noqa: E501

        :return: The inputs of this NodeMetaV0.
        :rtype: object
        """
        return self._inputs

    @inputs.setter
    def inputs(self, inputs: object):
        """Sets the inputs of this NodeMetaV0.

        definition of the inputs of this node  # noqa: E501

        :param inputs: The inputs of this NodeMetaV0.
        :type inputs: object
        """
        if inputs is None:
            raise ValueError("Invalid value for `inputs`, must not be `None`")  # noqa: E501

        self._inputs = inputs

    @property
    def outputs(self) -> object:
        """Gets the outputs of this NodeMetaV0.

        definition of the outputs of this node  # noqa: E501

        :return: The outputs of this NodeMetaV0.
        :rtype: object
        """
        return self._outputs

    @outputs.setter
    def outputs(self, outputs: object):
        """Sets the outputs of this NodeMetaV0.

        definition of the outputs of this node  # noqa: E501

        :param outputs: The outputs of this NodeMetaV0.
        :type outputs: object
        """
        if outputs is None:
            raise ValueError("Invalid value for `outputs`, must not be `None`")  # noqa: E501

        self._outputs = outputs
