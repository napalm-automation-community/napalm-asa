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

Read napalm.readthedocs.org for more information.
"""

from __future__ import unicode_literals

import ssl
import urllib2
import json
import base64
import re

# import third party lib
from netaddr import IPAddress
from netaddr import IPNetwork
from netaddr.core import AddrFormatError

from napalm_base.base import NetworkDriver
from napalm_base.exceptions import ConnectionException, SessionLockedException, \
                                   MergeConfigException, ReplaceConfigException,\
                                   CommandErrorException


ssl._create_default_https_context = ssl._create_unverified_context


class RespFetcherHttps:

    def __init__(
        self,
        username='admin',
        password='insieme',
        base_url='https://172.21.128.227/api',
        timeout=30
    ):

        self.username = username
        self.password = password
        self.base_url = base_url
        self.base64_str = base64.encodestring('%s:%s' % (username,
                                              password)).replace('\n', '')
        self.timeout = timeout
        self.headers = {'Content-Type': 'application/json'}

    def get_resp(self, endpoint="", data=None):

        full_url = self.base_url + endpoint
        req = urllib2.Request(full_url, data, self.headers)
        base64string = self.base64_str
        req.add_header("Authorization", "Basic %s" % base64string)
        f = None
        try:
            try:
                f = urllib2.urlopen(req, data, self.timeout)
                status_code = f.getcode()
                if (status_code != 200):
                    print 'Error in get. Got status code: '+status_code
                resp = f.read()
                json_resp = json.loads(resp)
                return json.dumps(json_resp, sort_keys=True, indent=4, separators=(',', ': '))
            finally:
                if f:
                    f.close()
        except urllib2.URLError, e:
            if hasattr(e, 'reason'):
                print 'Request failed.'
                print 'Reason: ', e.reason
                raise

            elif hasattr(e, 'code'):
                print 'Device responded with an error.'
                print 'Error code: ', e.code
                raise


class ASADriver(NetworkDriver):
    """Napalm driver for Cisco ASA."""

    def __init__(self,
                 hostname='192.168.200.50',
                 username='cisco',
                 password='cisco',
                 port='443',
                 timeout=30):

        self.username = username
        self.password = password
        self.hostname = hostname
        self.port = port
        self.timeout = timeout
        self.up = False
        self.base_url = 'https://' + self.hostname + ':' + self.port + '/api'
        self.device = RespFetcherHttps(self.username, self.password, self.base_url, self.timeout)

    def _send_request(self, endpoint, data=None):
        # url = self.base_url + endpoint
        # request = RespFetcherHttps(self.username, self.password, url, self.timeout)

        if data is None:
            response = self.device.get_resp(endpoint)
        else:
            response = self.device.get_resp(endpoint, json.dumps(data))

        parsed_response = json.loads(response)
        return parsed_response

    def _get_interfaces_details(self, interfaces):
        commands = []
        for interface in interfaces:
            commands.append("show interface " + interface)

        results = self.cli(commands)

        ifs_details = {}
        for command, details in results.items():
            if_name = re.search(r"show interface (.*)", command).group(1)
            mac = re.search(r"MAC address (.{14}),", details).group(1)

            match_if_status = re.search(r"line protocol is (.{2,4})\n", results[command])
            if match_if_status.group(1) == 'up':
                if_up = True
            else:
                if_up = False

            ifs_details[if_name] = {
                                'mac_address': mac,
                                'is_up': if_up
                                }

        return ifs_details

    def open(self):
        """
        This method can be used to verify if the device is reachable
        and credentials are valid before moving on to other, more complex,
        requests.
        """

        # api_endpoint = self.base_url + '/monitoring/serialnumber'
        # req = RespFetcherHttps(self.username, self.password, api_endpoint, self.timeout)
        sn = self._send_request('/monitoring/serialnumber')
        if sn['serialNumber'] is not None:
            self.up = True
            return True
        else:
            self.up = False
            return False

    def cli(self, commands):
        data = {
                  "commands": commands
                }

        response = self._send_request('/cli', data)

        result_dict = {}

        for i, result in enumerate(response['response']):
            result_dict[commands[i]] = result

        return result_dict

    def get_facts(self):
        facts = {
                'uptime': 0.0,
                'vendor': u'Cisco Systems',
                'os_version': u'',
                'serial_number': u'',
                'model': u'',
                'hostname': u'',
                'fqdn': u'',
                'interface_list': []
                }

        serialNumber = self._send_request('/monitoring/serialnumber')
        facts['serial_number'] = serialNumber['serialNumber']

        deviceDetails = self._send_request('/monitoring/device/components/version')
        facts['os_version'] = deviceDetails['asaVersion']
        facts['uptime'] = deviceDetails['upTimeinSeconds']
        facts['model'] = deviceDetails['deviceType']

        results_from_cli = self.cli(['show hostname', 'show hostname fqdn'])
        facts['hostname'] = results_from_cli['show hostname'].replace('\n', '')
        facts['fqdn'] = results_from_cli['show hostname fqdn'].replace('\n', '')

        interfaces = self.get_interfaces()

        for if_name in interfaces:
            facts['interface_list'].append(if_name)

        return facts

    def get_interfaces(self):
        interfaces = {}
        response = self._send_request('/interfaces/physical')

        if response['rangeInfo']['total'] > 0:

            for int_info in response['items']:
                interfaces[int_info['hardwareID']] = {
                    'is_up': False,
                    'is_enabled': not int_info['shutdown'],
                    'description': int_info['interfaceDesc'],
                    'last_flapped': -1.0,
                    'speed': 0,
                    'mac_address': u'',
                }

            ifs = []
            for if_name in interfaces:
                ifs.append(if_name)

            ifs_details = self._get_interfaces_details(ifs)

            for if_name, details in ifs_details.items():
                interfaces[if_name]['mac_address'] = details['mac_address']
                interfaces[if_name]['is_up'] = details['is_up']

        return interfaces

    def get_config(self):
        command = "show startup-config"
        results = self.cli([command])

        return results[command]

    def get_interfaces_ip(self):
        interfaces = {}
        response = self._send_request('/interfaces/physical')

        if response['rangeInfo']['total'] > 0:

            for int_info in response['items']:

                if int_info['ipAddress'] != "NoneSelected":
                    interfaces[int_info['hardwareID']] = {}
                    ipv4 = int_info['ipAddress']
                    ip = ipv4['ip']['value']
                    mask = ipv4['netMask']['value']
                    network = ip + '/' + mask
                    prefix_length = IPNetwork(network).prefixlen
                    interfaces[int_info['hardwareID']]['ipv4'] = {ip: {'prefix_length': prefix_length}}

                if len(int_info['ipv6Info']['ipv6Addresses']) > 0:
                    if int_info['hardwareID'] not in interfaces:
                        interfaces[int_info['hardwareID']] = {}

                    interfaces[int_info['hardwareID']]['ipv6'] = {}
                    for ipv6 in int_info['ipv6Info']['ipv6Addresses']:
                        ip = ipv6['address']['value']
                        prefix_length = ipv6['prefixLength']
                        interfaces[int_info['hardwareID']]['ipv6'][ip] = {'prefix_length': prefix_length}

        return interfaces
