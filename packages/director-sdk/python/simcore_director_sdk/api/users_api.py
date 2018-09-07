# coding: utf-8

"""
    Director API

    This is the oSparc's director API  # noqa: E501

    OpenAPI spec version: 1.0.0
    Contact: support@simcore.com
    Generated by: https://openapi-generator.tech
"""


from __future__ import absolute_import

import re  # noqa: F401

# python 2 and python 3 compatibility library
import six

from simcore_director_sdk.api_client import ApiClient


class UsersApi(object):
    """NOTE: This class is auto generated by OpenAPI Generator
    Ref: https://openapi-generator.tech

    Do not edit the class manually.
    """

    def __init__(self, api_client=None):
        if api_client is None:
            api_client = ApiClient()
        self.api_client = api_client

    def root_get(self, **kwargs):  # noqa: E501
        """Service health-check endpoint  # noqa: E501

        Some general information on the API and state of the service behind  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.root_get(async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :return: HealthCheckEnveloped
                 If the method is called asynchronously,
                 returns the request thread.
        """
        kwargs['_return_http_data_only'] = True
        if kwargs.get('async_req'):
            return self.root_get_with_http_info(**kwargs)  # noqa: E501
        else:
            (data) = self.root_get_with_http_info(**kwargs)  # noqa: E501
            return data

    def root_get_with_http_info(self, **kwargs):  # noqa: E501
        """Service health-check endpoint  # noqa: E501

        Some general information on the API and state of the service behind  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.root_get_with_http_info(async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :return: HealthCheckEnveloped
                 If the method is called asynchronously,
                 returns the request thread.
        """

        local_var_params = locals()

        all_params = []  # noqa: E501
        all_params.append('async_req')
        all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')

        for key, val in six.iteritems(local_var_params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method root_get" % key
                )
            local_var_params[key] = val
        del local_var_params['kwargs']

        collection_formats = {}

        path_params = {}

        query_params = []

        header_params = {}

        form_params = []
        local_var_files = {}

        body_params = None
        # HTTP header `Accept`
        header_params['Accept'] = self.api_client.select_header_accept(
            ['application/json'])  # noqa: E501

        # Authentication setting
        auth_settings = []  # noqa: E501

        return self.api_client.call_api(
            '/', 'GET',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type='HealthCheckEnveloped',  # noqa: E501
            auth_settings=auth_settings,
            async_req=local_var_params.get('async_req'),
            _return_http_data_only=local_var_params.get('_return_http_data_only'),  # noqa: E501
            _preload_content=local_var_params.get('_preload_content', True),
            _request_timeout=local_var_params.get('_request_timeout'),
            collection_formats=collection_formats)

    def running_interactive_services_delete(self, service_uuid, **kwargs):  # noqa: E501
        """Stops and removes an interactive service from the oSparc platform  # noqa: E501

        Stops and removes an interactive service from the oSparc platform  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.running_interactive_services_delete(service_uuid, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str service_uuid: The uuid of the service (required)
        :return: Response204Enveloped
                 If the method is called asynchronously,
                 returns the request thread.
        """
        kwargs['_return_http_data_only'] = True
        if kwargs.get('async_req'):
            return self.running_interactive_services_delete_with_http_info(service_uuid, **kwargs)  # noqa: E501
        else:
            (data) = self.running_interactive_services_delete_with_http_info(service_uuid, **kwargs)  # noqa: E501
            return data

    def running_interactive_services_delete_with_http_info(self, service_uuid, **kwargs):  # noqa: E501
        """Stops and removes an interactive service from the oSparc platform  # noqa: E501

        Stops and removes an interactive service from the oSparc platform  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.running_interactive_services_delete_with_http_info(service_uuid, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str service_uuid: The uuid of the service (required)
        :return: Response204Enveloped
                 If the method is called asynchronously,
                 returns the request thread.
        """

        local_var_params = locals()

        all_params = ['service_uuid']  # noqa: E501
        all_params.append('async_req')
        all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')

        for key, val in six.iteritems(local_var_params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method running_interactive_services_delete" % key
                )
            local_var_params[key] = val
        del local_var_params['kwargs']
        # verify the required parameter 'service_uuid' is set
        if ('service_uuid' not in local_var_params or
                local_var_params['service_uuid'] is None):
            raise ValueError("Missing the required parameter `service_uuid` when calling `running_interactive_services_delete`")  # noqa: E501

        collection_formats = {}

        path_params = {}
        if 'service_uuid' in local_var_params:
            path_params['service_uuid'] = local_var_params['service_uuid']  # noqa: E501

        query_params = []

        header_params = {}

        form_params = []
        local_var_files = {}

        body_params = None
        # HTTP header `Accept`
        header_params['Accept'] = self.api_client.select_header_accept(
            ['application/json'])  # noqa: E501

        # Authentication setting
        auth_settings = []  # noqa: E501

        return self.api_client.call_api(
            '/running_interactive_services/{service_uuid}', 'DELETE',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type='Response204Enveloped',  # noqa: E501
            auth_settings=auth_settings,
            async_req=local_var_params.get('async_req'),
            _return_http_data_only=local_var_params.get('_return_http_data_only'),  # noqa: E501
            _preload_content=local_var_params.get('_preload_content', True),
            _request_timeout=local_var_params.get('_request_timeout'),
            collection_formats=collection_formats)

    def running_interactive_services_get(self, service_uuid, **kwargs):  # noqa: E501
        """Succesfully returns if a service with the defined uuid is up and running  # noqa: E501

        Succesfully returns if a service with the defined uuid is up and running  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.running_interactive_services_get(service_uuid, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str service_uuid: The uuid of the service (required)
        :return: Response204Enveloped
                 If the method is called asynchronously,
                 returns the request thread.
        """
        kwargs['_return_http_data_only'] = True
        if kwargs.get('async_req'):
            return self.running_interactive_services_get_with_http_info(service_uuid, **kwargs)  # noqa: E501
        else:
            (data) = self.running_interactive_services_get_with_http_info(service_uuid, **kwargs)  # noqa: E501
            return data

    def running_interactive_services_get_with_http_info(self, service_uuid, **kwargs):  # noqa: E501
        """Succesfully returns if a service with the defined uuid is up and running  # noqa: E501

        Succesfully returns if a service with the defined uuid is up and running  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.running_interactive_services_get_with_http_info(service_uuid, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str service_uuid: The uuid of the service (required)
        :return: Response204Enveloped
                 If the method is called asynchronously,
                 returns the request thread.
        """

        local_var_params = locals()

        all_params = ['service_uuid']  # noqa: E501
        all_params.append('async_req')
        all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')

        for key, val in six.iteritems(local_var_params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method running_interactive_services_get" % key
                )
            local_var_params[key] = val
        del local_var_params['kwargs']
        # verify the required parameter 'service_uuid' is set
        if ('service_uuid' not in local_var_params or
                local_var_params['service_uuid'] is None):
            raise ValueError("Missing the required parameter `service_uuid` when calling `running_interactive_services_get`")  # noqa: E501

        collection_formats = {}

        path_params = {}
        if 'service_uuid' in local_var_params:
            path_params['service_uuid'] = local_var_params['service_uuid']  # noqa: E501

        query_params = []

        header_params = {}

        form_params = []
        local_var_files = {}

        body_params = None
        # HTTP header `Accept`
        header_params['Accept'] = self.api_client.select_header_accept(
            ['application/json'])  # noqa: E501

        # Authentication setting
        auth_settings = []  # noqa: E501

        return self.api_client.call_api(
            '/running_interactive_services/{service_uuid}', 'GET',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type='Response204Enveloped',  # noqa: E501
            auth_settings=auth_settings,
            async_req=local_var_params.get('async_req'),
            _return_http_data_only=local_var_params.get('_return_http_data_only'),  # noqa: E501
            _preload_content=local_var_params.get('_preload_content', True),
            _request_timeout=local_var_params.get('_request_timeout'),
            collection_formats=collection_formats)

    def running_interactive_services_post(self, service_key, service_uuid, **kwargs):  # noqa: E501
        """Starts an interactive service in the oSparc platform and returns its entrypoint  # noqa: E501

        Starts an interactive service in the oSparc platform and returns its entrypoint  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.running_interactive_services_post(service_key, service_uuid, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str service_key: The key (url) of the service (required)
        :param str service_uuid: The uuid to assign the service with (required)
        :param str service_tag: The tag/version of the service
        :return: RunningServiceEnveloped
                 If the method is called asynchronously,
                 returns the request thread.
        """
        kwargs['_return_http_data_only'] = True
        if kwargs.get('async_req'):
            return self.running_interactive_services_post_with_http_info(service_key, service_uuid, **kwargs)  # noqa: E501
        else:
            (data) = self.running_interactive_services_post_with_http_info(service_key, service_uuid, **kwargs)  # noqa: E501
            return data

    def running_interactive_services_post_with_http_info(self, service_key, service_uuid, **kwargs):  # noqa: E501
        """Starts an interactive service in the oSparc platform and returns its entrypoint  # noqa: E501

        Starts an interactive service in the oSparc platform and returns its entrypoint  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.running_interactive_services_post_with_http_info(service_key, service_uuid, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str service_key: The key (url) of the service (required)
        :param str service_uuid: The uuid to assign the service with (required)
        :param str service_tag: The tag/version of the service
        :return: RunningServiceEnveloped
                 If the method is called asynchronously,
                 returns the request thread.
        """

        local_var_params = locals()

        all_params = ['service_key', 'service_uuid', 'service_tag']  # noqa: E501
        all_params.append('async_req')
        all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')

        for key, val in six.iteritems(local_var_params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method running_interactive_services_post" % key
                )
            local_var_params[key] = val
        del local_var_params['kwargs']
        # verify the required parameter 'service_key' is set
        if ('service_key' not in local_var_params or
                local_var_params['service_key'] is None):
            raise ValueError("Missing the required parameter `service_key` when calling `running_interactive_services_post`")  # noqa: E501
        # verify the required parameter 'service_uuid' is set
        if ('service_uuid' not in local_var_params or
                local_var_params['service_uuid'] is None):
            raise ValueError("Missing the required parameter `service_uuid` when calling `running_interactive_services_post`")  # noqa: E501

        collection_formats = {}

        path_params = {}

        query_params = []
        if 'service_key' in local_var_params:
            query_params.append(('service_key', local_var_params['service_key']))  # noqa: E501
        if 'service_tag' in local_var_params:
            query_params.append(('service_tag', local_var_params['service_tag']))  # noqa: E501
        if 'service_uuid' in local_var_params:
            query_params.append(('service_uuid', local_var_params['service_uuid']))  # noqa: E501

        header_params = {}

        form_params = []
        local_var_files = {}

        body_params = None
        # HTTP header `Accept`
        header_params['Accept'] = self.api_client.select_header_accept(
            ['application/json'])  # noqa: E501

        # Authentication setting
        auth_settings = []  # noqa: E501

        return self.api_client.call_api(
            '/running_interactive_services', 'POST',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type='RunningServiceEnveloped',  # noqa: E501
            auth_settings=auth_settings,
            async_req=local_var_params.get('async_req'),
            _return_http_data_only=local_var_params.get('_return_http_data_only'),  # noqa: E501
            _preload_content=local_var_params.get('_preload_content', True),
            _request_timeout=local_var_params.get('_request_timeout'),
            collection_formats=collection_formats)

    def services_get(self, **kwargs):  # noqa: E501
        """Lists available services in the oSparc platform  # noqa: E501

        Lists available services in the oSparc platform  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.services_get(async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str service_type: The service type:   * computational - a computational service   * interactive - an interactive service 
        :return: ServicesEnveloped
                 If the method is called asynchronously,
                 returns the request thread.
        """
        kwargs['_return_http_data_only'] = True
        if kwargs.get('async_req'):
            return self.services_get_with_http_info(**kwargs)  # noqa: E501
        else:
            (data) = self.services_get_with_http_info(**kwargs)  # noqa: E501
            return data

    def services_get_with_http_info(self, **kwargs):  # noqa: E501
        """Lists available services in the oSparc platform  # noqa: E501

        Lists available services in the oSparc platform  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.services_get_with_http_info(async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str service_type: The service type:   * computational - a computational service   * interactive - an interactive service 
        :return: ServicesEnveloped
                 If the method is called asynchronously,
                 returns the request thread.
        """

        local_var_params = locals()

        all_params = ['service_type']  # noqa: E501
        all_params.append('async_req')
        all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')

        for key, val in six.iteritems(local_var_params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method services_get" % key
                )
            local_var_params[key] = val
        del local_var_params['kwargs']

        collection_formats = {}

        path_params = {}

        query_params = []
        if 'service_type' in local_var_params:
            query_params.append(('service_type', local_var_params['service_type']))  # noqa: E501

        header_params = {}

        form_params = []
        local_var_files = {}

        body_params = None
        # HTTP header `Accept`
        header_params['Accept'] = self.api_client.select_header_accept(
            ['application/json'])  # noqa: E501

        # Authentication setting
        auth_settings = []  # noqa: E501

        return self.api_client.call_api(
            '/services', 'GET',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type='ServicesEnveloped',  # noqa: E501
            auth_settings=auth_settings,
            async_req=local_var_params.get('async_req'),
            _return_http_data_only=local_var_params.get('_return_http_data_only'),  # noqa: E501
            _preload_content=local_var_params.get('_preload_content', True),
            _request_timeout=local_var_params.get('_request_timeout'),
            collection_formats=collection_formats)
