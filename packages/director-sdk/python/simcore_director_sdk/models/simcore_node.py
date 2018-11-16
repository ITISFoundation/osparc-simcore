# coding: utf-8

"""
    Director API

    This is the oSparc's director API  # noqa: E501

    OpenAPI spec version: 1.0.0
    Contact: support@simcore.com
    Generated by: https://openapi-generator.tech
"""


import pprint
import re  # noqa: F401

import six


class SimcoreNode(object):
    """NOTE: This class is auto generated by OpenAPI Generator.
    Ref: https://openapi-generator.tech

    Do not edit the class manually.
    """

    """
    Attributes:
      openapi_types (dict): The key is attribute name
                            and the value is attribute type.
      attribute_map (dict): The key is attribute name
                            and the value is json key in definition.
    """
    openapi_types = {
        'authors': 'list[InlineResponse2001Authors]',
        'contact': 'str',
        'description': 'str',
        'inputs': 'object',
        'key': 'str',
        'name': 'str',
        'outputs': 'object',
        'type': 'str',
        'version': 'str'
    }

    attribute_map = {
        'authors': 'authors',
        'contact': 'contact',
        'description': 'description',
        'inputs': 'inputs',
        'key': 'key',
        'name': 'name',
        'outputs': 'outputs',
        'type': 'type',
        'version': 'version'
    }

    def __init__(self, authors=None, contact=None, description=None, inputs=None, key=None, name=None, outputs=None, type=None, version=None):  # noqa: E501
        """SimcoreNode - a model defined in OpenAPI"""  # noqa: E501

        self._authors = None
        self._contact = None
        self._description = None
        self._inputs = None
        self._key = None
        self._name = None
        self._outputs = None
        self._type = None
        self._version = None
        self.discriminator = None

        self.authors = authors
        self.contact = contact
        self.description = description
        self.inputs = inputs
        self.key = key
        self.name = name
        self.outputs = outputs
        self.type = type
        self.version = version

    @property
    def authors(self):
        """Gets the authors of this SimcoreNode.  # noqa: E501


        :return: The authors of this SimcoreNode.  # noqa: E501
        :rtype: list[InlineResponse2001Authors]
        """
        return self._authors

    @authors.setter
    def authors(self, authors):
        """Sets the authors of this SimcoreNode.


        :param authors: The authors of this SimcoreNode.  # noqa: E501
        :type: list[InlineResponse2001Authors]
        """
        if authors is None:
            raise ValueError("Invalid value for `authors`, must not be `None`")  # noqa: E501

        self._authors = authors

    @property
    def contact(self):
        """Gets the contact of this SimcoreNode.  # noqa: E501

        email to correspond to the authors about the node  # noqa: E501

        :return: The contact of this SimcoreNode.  # noqa: E501
        :rtype: str
        """
        return self._contact

    @contact.setter
    def contact(self, contact):
        """Sets the contact of this SimcoreNode.

        email to correspond to the authors about the node  # noqa: E501

        :param contact: The contact of this SimcoreNode.  # noqa: E501
        :type: str
        """
        if contact is None:
            raise ValueError("Invalid value for `contact`, must not be `None`")  # noqa: E501

        self._contact = contact

    @property
    def description(self):
        """Gets the description of this SimcoreNode.  # noqa: E501

        human readable description of the purpose of the node  # noqa: E501

        :return: The description of this SimcoreNode.  # noqa: E501
        :rtype: str
        """
        return self._description

    @description.setter
    def description(self, description):
        """Sets the description of this SimcoreNode.

        human readable description of the purpose of the node  # noqa: E501

        :param description: The description of this SimcoreNode.  # noqa: E501
        :type: str
        """
        if description is None:
            raise ValueError("Invalid value for `description`, must not be `None`")  # noqa: E501

        self._description = description

    @property
    def inputs(self):
        """Gets the inputs of this SimcoreNode.  # noqa: E501

        definition of the inputs of this node  # noqa: E501

        :return: The inputs of this SimcoreNode.  # noqa: E501
        :rtype: object
        """
        return self._inputs

    @inputs.setter
    def inputs(self, inputs):
        """Sets the inputs of this SimcoreNode.

        definition of the inputs of this node  # noqa: E501

        :param inputs: The inputs of this SimcoreNode.  # noqa: E501
        :type: object
        """
        if inputs is None:
            raise ValueError("Invalid value for `inputs`, must not be `None`")  # noqa: E501

        self._inputs = inputs

    @property
    def key(self):
        """Gets the key of this SimcoreNode.  # noqa: E501

        distinctive name for the node based on the docker registry path  # noqa: E501

        :return: The key of this SimcoreNode.  # noqa: E501
        :rtype: str
        """
        return self._key

    @key.setter
    def key(self, key):
        """Sets the key of this SimcoreNode.

        distinctive name for the node based on the docker registry path  # noqa: E501

        :param key: The key of this SimcoreNode.  # noqa: E501
        :type: str
        """
        if key is None:
            raise ValueError("Invalid value for `key`, must not be `None`")  # noqa: E501
        if key is not None and not re.search('^(simcore)\/(services)\/(comp|dynamic)(\/[^\\s\/]+)+$', key):  # noqa: E501
            raise ValueError("Invalid value for `key`, must be a follow pattern or equal to `/^(simcore)\/(services)\/(comp|dynamic)(\/[^\\s\/]+)+$/`")  # noqa: E501

        self._key = key

    @property
    def name(self):
        """Gets the name of this SimcoreNode.  # noqa: E501

        short, human readable name for the node  # noqa: E501

        :return: The name of this SimcoreNode.  # noqa: E501
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, name):
        """Sets the name of this SimcoreNode.

        short, human readable name for the node  # noqa: E501

        :param name: The name of this SimcoreNode.  # noqa: E501
        :type: str
        """
        if name is None:
            raise ValueError("Invalid value for `name`, must not be `None`")  # noqa: E501

        self._name = name

    @property
    def outputs(self):
        """Gets the outputs of this SimcoreNode.  # noqa: E501

        definition of the outputs of this node  # noqa: E501

        :return: The outputs of this SimcoreNode.  # noqa: E501
        :rtype: object
        """
        return self._outputs

    @outputs.setter
    def outputs(self, outputs):
        """Sets the outputs of this SimcoreNode.

        definition of the outputs of this node  # noqa: E501

        :param outputs: The outputs of this SimcoreNode.  # noqa: E501
        :type: object
        """
        if outputs is None:
            raise ValueError("Invalid value for `outputs`, must not be `None`")  # noqa: E501

        self._outputs = outputs

    @property
    def type(self):
        """Gets the type of this SimcoreNode.  # noqa: E501

        service type  # noqa: E501

        :return: The type of this SimcoreNode.  # noqa: E501
        :rtype: str
        """
        return self._type

    @type.setter
    def type(self, type):
        """Sets the type of this SimcoreNode.

        service type  # noqa: E501

        :param type: The type of this SimcoreNode.  # noqa: E501
        :type: str
        """
        if type is None:
            raise ValueError("Invalid value for `type`, must not be `None`")  # noqa: E501
        allowed_values = ["computational", "dynamic"]  # noqa: E501
        if type not in allowed_values:
            raise ValueError(
                "Invalid value for `type` ({0}), must be one of {1}"  # noqa: E501
                .format(type, allowed_values)
            )

        self._type = type

    @property
    def version(self):
        """Gets the version of this SimcoreNode.  # noqa: E501

        semantic version number  # noqa: E501

        :return: The version of this SimcoreNode.  # noqa: E501
        :rtype: str
        """
        return self._version

    @version.setter
    def version(self, version):
        """Sets the version of this SimcoreNode.

        semantic version number  # noqa: E501

        :param version: The version of this SimcoreNode.  # noqa: E501
        :type: str
        """
        if version is None:
            raise ValueError("Invalid value for `version`, must not be `None`")  # noqa: E501
        if version is not None and not re.search('^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$', version):  # noqa: E501
            raise ValueError(r"Invalid value for `version`, must be a follow pattern or equal to `/^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$/`")  # noqa: E501

        self._version = version

    def to_dict(self):
        """Returns the model properties as a dict"""
        result = {}

        for attr, _ in six.iteritems(self.openapi_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, "to_dict") else x,
                    value
                ))
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], "to_dict") else item,
                    value.items()
                ))
            else:
                result[attr] = value

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, SimcoreNode):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
