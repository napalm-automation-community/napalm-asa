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
import re
import json
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from collections import OrderedDict

# import third party lib
from netaddr import IPNetwork

# Napalm base imports
from napalm.base.helpers import sanitize_configs
from napalm.base import NetworkDriver
from napalm.base.exceptions import (
    ConnectionException,
    CommandErrorException,
)
from napalm_asa._SUPPORTED_INTERFACES_ENDPOINTS import SUPPORTED_INTERFACES_ENDPOINTS
from napalm_asa.constants import ASA_SANITIZE_FILTERS

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class RespFetcherHttps:
    """Response fetcher."""

    def __init__(
        self,
        username="admin",
        password="insieme",
        base_url="https://172.21.128.227/api",
        timeout=30,
    ):
        """Class init."""
        self.username = username
        self.password = password
        self.base_url = base_url
        self.timeout = timeout
        self.token = ""
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def get_auth_token(self):
        """ Authenticate with user and password to get an auth token."""
        full_url = self.base_url + "/tokenservices"
        try:
            token_request = self.session.post(
                full_url,
                auth=(self.username, self.password),
                data="",
                timeout=self.timeout,
                verify=False,
            )
            if (
                token_request.status_code == 204
                and "X-Auth-Token" in token_request.headers.keys()
            ):
                self.token = token_request.headers["X-Auth-Token"]
                self.session.headers.update(
                    {"X-Auth-Token": token_request.headers["X-Auth-Token"]}
                )
                return (True, None)
            else:
                return (False, token_request.status_code)
        except requests.exceptions.RequestException as e:
            raise ConnectionException(str(e))

    def delete_token(self):
        """Delete auth token."""
        full_url = self.base_url + "/tokenservices/{}".format(self.token)
        try:
            token_delete_request = self.session.delete(
                full_url,
                auth=(self.username, self.password),
                timeout=self.timeout,
                verify=False,
            )
            if token_delete_request.status_code == 204:
                self.session.headers.pop("X-Auth-Token", None)
                return (True, None)
            else:
                return (False, token_delete_request.status_code)
        except requests.exceptions.RequestException as e:
            raise ConnectionException(str(e))

    def get_resp(self, endpoint="", data=None, params={}, throw=True):
        """Get response from device and returne parsed json."""
        full_url = self.base_url + endpoint
        f = None
        try:
            if data is not None:
                f = self.session.post(
                    full_url,
                    data=data,
                    headers=self.headers,
                    timeout=self.timeout,
                    params=params,
                    verify=False,
                )
            else:
                f = self.session.get(
                    full_url,
                    headers=self.headers,
                    timeout=self.timeout,
                    params=params,
                    verify=False,
                )
            if f.status_code != 200:
                if throw:
                    errMsg = "Operation returned an error: {}".format(f.status_code)
                    raise CommandErrorException(errMsg)
                else:
                    return False

            return f.json()
        except requests.exceptions.RequestException as e:
            if throw:
                raise ConnectionException(str(e))
            else:
                return False

    def has_active_token(self):
        status = False
        if "X-Auth-Token" in self.session.headers:
            response = self.get_resp("/monitoring/serialnumber", throw=False)
            if "kind" in response and response["kind"] == "object#QuerySerialNumber":
                status = True

        return status


class ASADriver(NetworkDriver):
    """Napalm driver for Cisco ASA."""

    def __init__(self, hostname, username, password, timeout=60, optional_args=None):
        """Class init."""
        optional_args = optional_args or dict()
        self.username = username
        self.password = password
        self.hostname = hostname
        self.port = optional_args.get("port", 443)
        self.timeout = timeout
        self.up = False
        self.base_url = "https://{}:{}/api".format(self.hostname, self.port)
        self.device = RespFetcherHttps(
            self.username, self.password, self.base_url, self.timeout
        )

    def _authenticate(self):
        """Authenticate with device."""
        auth_result = self.device.get_auth_token()

        return auth_result

    def _delete_token(self):
        """Delete auth token."""

        delete_result = self.device.delete_token()

        return delete_result

    def _send_request(self, endpoint, data=None, throw=True):
        """Send request method."""
        if data is None:
            response = self.device.get_resp(endpoint)
        else:
            response = self.device.get_resp(endpoint, json.dumps(data))

        if "rangeInfo" in response:
            if response["rangeInfo"]["limit"] < response["rangeInfo"]["total"]:
                fetched_items = len(response["items"])
                while fetched_items < response["rangeInfo"]["total"]:
                    offset = fetched_items
                    params = {"offset": offset}
                    if data is None:
                        r = self.device.get_resp(
                            endpoint=endpoint, params=params, throw=throw
                        )
                    else:
                        r = self.device.get_resp(
                            endpoint=endpoint,
                            data=json.dumps(data),
                            params=params,
                            throw=throw,
                        )

                    fetched_items = fetched_items + len(r["items"])
                    response["items"] = response["items"] + r["items"]

        return response

    def _get_interfaces_details(self, interfaces):
        commands = []
        for interface in interfaces:
            commands.append("show interface " + interface)

        results = self.cli(commands)

        ifs_details = {}
        for command, details in results.items():
            if_name = re.search(r"show interface (.*)", command).group(1)
            match_mac = re.search(r"MAC address (.{14}),", details)
            mac = ""
            if match_mac is not None:
                mac = match_mac.group(1)

            match_if_status = re.search(
                r"line protocol is (.{2,4})\n", results[command]
            )
            if match_if_status.group(1) == "up":
                if_up = True
            else:
                if_up = False

            match_mtu = re.search(r"MTU (.{1,4})\n", details)
            mtu = 0
            if match_mtu is not None:
                mtu = int(match_mtu.group(1))

            ifs_details[if_name] = {"mac_address": mac, "is_up": if_up, "mtu": mtu}

        return ifs_details

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
            raise ConnectionException(
                "Cannot connect to {}. Error {}".format(self.hostname, code)
            )

    def close(self):
        """Mark the connection to the device as closed."""
        delete_result, code = self._delete_token()

        if delete_result:
            self.up = False
            return True
        else:
            raise ConnectionException(
                "Cannot connect to {}. Error {}".format(self.hostname, code)
            )

    def cli(self, commands):
        """Run CLI commands via the API."""
        data = {"commands": commands}

        response = self._send_request("/cli", data)

        result_dict = {}

        for i, result in enumerate(response["response"]):
            result_dict[commands[i]] = result

        return result_dict

    def get_facts(self):
        """Get Facts."""
        facts = {
            "uptime": 0.0,
            "vendor": "Cisco Systems",
            "os_version": "",
            "serial_number": "",
            "model": "",
            "hostname": "",
            "fqdn": "",
            "interface_list": [],
        }

        serialNumber = self._send_request("/monitoring/serialnumber")
        facts["serial_number"] = serialNumber["serialNumber"]

        deviceDetails = self._send_request("/monitoring/device/components/version")
        facts["os_version"] = deviceDetails["asaVersion"]
        facts["uptime"] = deviceDetails["upTimeinSeconds"]
        facts["model"] = deviceDetails["deviceType"]

        results_from_cli = self.cli(["show hostname", "show hostname fqdn"])
        facts["hostname"] = results_from_cli["show hostname"].replace("\n", "")
        facts["fqdn"] = results_from_cli["show hostname fqdn"].replace("\n", "")

        interfaces = self.get_interfaces()

        for if_name in interfaces:
            facts["interface_list"].append(if_name)

        return facts

    def get_interfaces(self):
        """Get Interfaces."""
        interfaces = OrderedDict()
        responses = []

        for endpoint in SUPPORTED_INTERFACES_ENDPOINTS:
            responses.append(self._send_request(endpoint, throw=False))

        for response in responses:
            if response["rangeInfo"]["total"] > 0:

                for int_info in response["items"]:
                    interfaces[int_info["hardwareID"]] = {
                        "is_up": False,
                        "is_enabled": not int_info["shutdown"],
                        "description": int_info["interfaceDesc"],
                        "last_flapped": -1.0,
                        "speed": 0,
                        "mtu": 0,
                        "mac_address": "",
                    }

        ifs = []
        for if_name in interfaces:
            ifs.append(if_name)

        ifs_details = self._get_interfaces_details(ifs)

        for if_name, details in ifs_details.items():
            interfaces[if_name]["mac_address"] = details["mac_address"]
            interfaces[if_name]["is_up"] = details["is_up"]
            interfaces[if_name]["mtu"] = details["mtu"]

        return interfaces

    def get_config(self, retrieve="all", full=False, sanitized=False):
        """Get config."""
        config = {"startup": "", "running": "", "candidate": ""}

        commands = []
        startup_cmd = "show startup-config"
        running_cmd = "show running-config"

        if retrieve.lower() in ["startup", "all"]:
            commands.append(startup_cmd)
        if retrieve.lower() in ["running", "all"]:
            commands.append(running_cmd)

        if retrieve.lower() in ["running", "startup", "all"]:
            results = self.cli(commands)

        if retrieve.lower() in ["startup", "all"]:
            config["startup"] = results[startup_cmd]
        if retrieve.lower() in ["running", "all"]:
            config["running"] = results[running_cmd]

        if sanitized:
            return sanitize_configs(config, ASA_SANITIZE_FILTERS)

        return config

    def get_interfaces_ip(self):
        """Get interfaces ip."""
        interfaces = {}
        responses = []

        for endpoint in SUPPORTED_INTERFACES_ENDPOINTS:
            responses.append(self._send_request(endpoint, throw=False))

        for response in responses:
            if response["rangeInfo"]["total"] > 0:
                for int_info in response["items"]:
                    if int_info["ipAddress"] != "NoneSelected":
                        interfaces[int_info["hardwareID"]] = {}
                        ipv4 = int_info["ipAddress"]
                        ip = ipv4["ip"]["value"]
                        mask = ipv4["netMask"]["value"]
                        network = ip + "/" + mask
                        prefix_length = IPNetwork(network).prefixlen
                        interfaces[int_info["hardwareID"]]["ipv4"] = {
                            ip: {"prefix_length": prefix_length}
                        }

                    if len(int_info["ipv6Info"]["ipv6Addresses"]) > 0:
                        if int_info["hardwareID"] not in interfaces:
                            interfaces[int_info["hardwareID"]] = {}

                        interfaces[int_info["hardwareID"]]["ipv6"] = {}
                        for ipv6 in int_info["ipv6Info"]["ipv6Addresses"]:
                            ip = ipv6["address"]["value"]
                            prefix_length = ipv6["prefixLength"]
                            interfaces[int_info["hardwareID"]]["ipv6"][ip] = {
                                "prefix_length": prefix_length
                            }

        return interfaces

    def get_arp_table(self, vrf=""):
        """Get ARP Table."""
        arp_table = []
        response = self._send_request("/monitoring/arp")

        if response["rangeInfo"]["total"] > 0:
            for item in response["items"]:
                mac = item["macAddress"].replace(".", "")
                regex = re.compile(r".{2}")
                mac = ":".join(re.findall(regex, mac))
                arp_table.append(
                    {
                        "interface": item["interface"],
                        "ip": item["ipAddress"],
                        "mac": mac,
                        "age": 0.0,
                    }
                )

        return arp_table

    def is_alive(self):
        """Check if connection is still valid."""
        status = {"is_alive": self.device.has_active_token()}

        return status
