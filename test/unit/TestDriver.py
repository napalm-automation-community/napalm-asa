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

"""Tests."""

import unittest

from napalm_asa import asa
from napalm.base.test.base import TestConfigNetworkDriver, TestGettersNetworkDriver
import json
import re


class TestConfigDriver(unittest.TestCase, TestConfigNetworkDriver):
    """Group of tests that test Configuration related methods."""

    @classmethod
    def setUpClass(cls):
        """Run before starting the tests."""
        hostname = '127.0.0.1'
        username = 'vagrant'
        password = 'vagrant'
        cls.vendor = 'asa'

        optional_args = {'port': 12443, }
        cls.device = asa.ASADriver(hostname, username, password, timeout=60,
                                   optional_args=optional_args)
        cls.device.open()

        cls.device.load_replace_candidate(filename='%s/initial.conf' % cls.vendor)
        cls.device.commit_config()


class TestGetterDriver(unittest.TestCase, TestGettersNetworkDriver):
    """Group of tests that test getters."""

    @classmethod
    def setUpClass(cls):
        """Run before starting the tests."""
        cls.mock = True

        hostname = '127.0.0.1'
        username = 'vagrant'
        password = 'vagrant'
        cls.vendor = 'asa'

        optional_args = {'port': 443, }
        cls.device = asa.ASADriver(hostname, username, password, timeout=60,
                                   optional_args=optional_args)

        if cls.mock:
            cls.device.device = FakeDevice()
        else:
            cls.device.open()


class FakeDevice:
    """Test double."""

    @staticmethod
    def read_json_file(filename):
        """Return the content of a file with content formatted as json."""
        with open(filename) as data_file:
            return json.load(data_file)

    @staticmethod
    def read_txt_file(filename):
        """Return the content of a file."""
        with open(filename) as data_file:
            return data_file.read()

    def get_resp(self, endpoint="", data=None):
        """Fake method to read from file instead of connecting to device."""
        filename = re.sub(r'\/', '_', endpoint)

        if data is not None:
            parsed_data = json.loads(data)
            if "commands" in parsed_data:
                list_of_commands = parsed_data.get("commands")
                for command in list_of_commands:
                    cmd = re.sub(r'[\[\]\*\^\+\s\|\/]', '_', command)
                    filename += '_{}'.format(cmd)

        output = self.read_json_file('asa/mock_data/{}.json'.format(filename))
        """Fake na API request to the device by just returning the content of a file."""
        return output
