# -*- coding: utf-8 -*-
# Copyright 2016 Dravetech AB. All rights reserved.
#
# The contents of this file are licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
"""
Napalm driver for Cisco ASA.

Read https://napalm.readthedocs.io for more information.
"""

from __future__ import unicode_literals

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import json
import base64
import re
from string import whitespace
from collections import OrderedDict
from netaddr import IPNetwork

# import third party lib
from netaddr import IPNetwork

from napalm.base import NetworkDriver
from napalm.base.utils import py23_compat
from napalm.base.exceptions import (
    ConnectionException,
    CommandErrorException,
)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

IPV4_ADDR_REGEX = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"

class RespFetcherHttps:
    """Response fetcher."""

    def __init__(
        self,
        username='cisco',
        password='cisco',
        base_url='https://172.21.128.227/admin/config',
        timeout=30
    ):
        """Class init."""
        self.username = username
        self.password = password
        self.base_url = base_url
        self.timeout = timeout
        self.token = ""
        self.session = requests.Session()
        self.headers = {'Content-Type': 'text/xml'}

    def test_connection(self):
        """ Test connection to ASA via the ASDM Interface"""
        response = self.get_resp(endpoint="/show+version", returnObject=True)

        if response.status_code is 200:
            return (True, 200)
        else:
            return (False, response.status_code)

        return response 
        
    def get_resp(self, endpoint="", data=None, params={}, throw=True, returnObject=False):
        """Get response from device and returne parsed json."""
        full_url = self.base_url + endpoint
        f = None
        try:
            if data is not None:
                f = self.session.post(full_url, data=data, auth=(self.username, self.password),
                                      headers=self.headers, timeout=self.timeout,
                                      params=params, verify=False)
            else:
                f = self.session.get(full_url, auth=(self.username, self.password),
                                     headers=self.headers, timeout=self.timeout,
                                     params=params, verify=False)
            if (f.status_code != 200):
                if throw:
                    errMsg = "Operation returned an error: {}".format(f.status_code)
                    raise CommandErrorException(errMsg)
                else:
                    return False

            if returnObject:
                return f
            else:
                return f.text
        except requests.exceptions.RequestException as e:
            if throw:
                raise ConnectionException(py23_compat.text_type(e))
            else:
                return False

class ASADriver(NetworkDriver):
    """Napalm driver for Cisco ASA."""

    def __init__(self,
                 hostname,
                 username,
                 password,
                 timeout=60,
                 optional_args=None):
        """Class init."""
        optional_args = optional_args or dict()
        self.username = username
        self.password = password
        self.hostname = hostname
        self.port = optional_args.get('port', 443)
        self.timeout = timeout
        self.up = False
        self.base_url = "https://{}:{}/admin/exec".format(self.hostname, self.port)
        self.device = RespFetcherHttps(self.username, self.password, self.base_url, self.timeout)

    def _authenticate(self):
        """Authenticate with device."""
        auth_result = self.device.test_connection()

        return auth_result

    def _send_request(self, endpoint, data=None):
        """Send request method."""
        if data is None:
            response = self.device.get_resp(endpoint)
        else:
            response = self.device.get_resp(endpoint, json.dumps(data))

        return response

    def open(self):
        """
        Open a connection to the device.

        This method can be used to verify if the device is reachable
        and credentials are valid before moving on to other, more complex,
        requests.
        """
        auth_result, code = self._authenticate()
        if auth_result:
            self.up = True
            return True
        else:
            self.up = False
            raise ConnectionException('Cannot connect to {}. Error {}'.format(self.hostname, code))

    def close(self):
        """Mark the connection to the device as closed."""

        self.up = False
        return True

    def cli(self, commands):
        """Run CLI commands via the API."""
        data = {
                  "commands": commands
                }

        response = self._send_request('/cli', data)

        result_dict = {}

        for i, result in enumerate(response['response']):
            result_dict[commands[i]] = result

        return result_dict

    def get_interfaces_ip(self):
        """Get interfaces ip."""
        interfaces = {}
        show_interface = self._send_request('/show+interface')

        INTERNET_ADDRESS = r'\s+(?:IP address|Secondary address)'
        INTERNET_ADDRESS += r' (?P<ip>{}), subnet mask (?P<mask>{})'.format(IPV4_ADDR_REGEX, IPV4_ADDR_REGEX)
        # LINK_LOCAL_ADDRESS = r'\s+IPv6 is enabled, link-local address is (?P<ip>[a-fA-F0-9:]+)'
        # GLOBAL_ADDRESS = r'\s+(?P<ip>[a-fA-F0-9:]+), subnet is (?:[a-fA-F0-9:]+)/(?P<prefix>\d+)'

        for line in show_interface.splitlines():
            if(len(line.strip()) == 0):
                continue
            if(line[0] not in whitespace):
                ipv4 = {}
                interface_name = line.split()[1]
            m = re.match(INTERNET_ADDRESS, line)
            if m:
                ip, prefix = m.groups()
                ip_network = IPNetwork("{}/{}".format(ip,prefix))
                ipv4.update({ip: {"prefix_length": ip_network.prefixlen}})
                interfaces[interface_name] = {'ipv4': ipv4}

        return interfaces

    def is_alive(self):
        """Check if connection is still valid."""
        alive, code = self.device.test_connection()
        status = {"is_alive": alive }

        return status
