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

"""Tests for ASADriver."""

from __future__ import print_function
from __future__ import unicode_literals

from builtins import super

import pytest
from napalm_base.test import conftest as parent_conftest

from napalm_base.test.double import BaseTestDouble

from napalm_asa import asa
import json
import re


@pytest.fixture(scope='class')
def set_device_parameters(request):
    """Set up the class."""
    def fin():
        request.cls.device.close()
    request.addfinalizer(fin)

    request.cls.driver = asa.ASADriver
    request.cls.patched_driver = PatchedASADriver
    request.cls.vendor = 'asa'
    parent_conftest.set_device_parameters(request)


def pytest_generate_tests(metafunc):
    """Generate test cases dynamically."""
    parent_conftest.pytest_generate_tests(metafunc, __file__)


class PatchedASADriver(asa.ASADriver):
    """Patched ASA Driver."""

    def __init__(self, hostname, username, password, timeout=60, optional_args=None):

        super().__init__(hostname, username, password, timeout, optional_args)

        self.patched_attrs = ['device']
        self.device = FakeDevice()

    def is_alive(self):
        return {
            'is_alive': True  # In testing everything works..
        }

    def open(self):
        pass

    def close(self):
        pass


class FakeDevice(BaseTestDouble):
    """ASA Device Test double."""

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

    def close(self):
        pass

    @staticmethod
    def read_json_file(filename):
        """Return the content of a file with content formatted as json."""
        with open(filename) as data_file:
            return data_file.read()

    def get_resp(self, endpoint="", data=None):
        filename = re.sub(r'\/', '_', endpoint)

        if data is not None:
            parsed_data = json.loads(data)
            if "commands" in parsed_data:
                list_of_commands = parsed_data.get("commands")
                for command in list_of_commands:
                    cmd = re.sub(r'[\[\]\*\^\+\s\|\/]', '_', command)
                    filename += '_{}'.format(cmd)
        output = self.read_json_file('test/unit/asa/mock_data/{}.json'.format(filename))
        """Fake an API request to the device by just returning the content of a file."""
        return output
