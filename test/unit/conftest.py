"""Test fixtures."""
from builtins import super

import pytest
from napalm.base.test import conftest as parent_conftest

from napalm.base.test.double import BaseTestDouble

from napalm_asa import asa
import sys
import re
import requests
import requests_mock


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
        """Patched ASA Driver constructor."""
        super().__init__(hostname, username, password, timeout, optional_args)

        self.patched_attrs = ['device']
        self.device = FakeASADevice()

    def _authenticate(self):
        """Fake token authentication"""

        return (True, None)

    def _delete_token(self):
        """Fake Delete auth token."""

        return (True, None)


class FakeASADevice(BaseTestDouble):
    """ASA device test double."""

    def get_resp(self, endpoint="", returnObject=False):
        """Fake an API request to the device by just returning the contents of a file."""

        full_url = "mock://asa.cisco" + endpoint

        filename = re.sub(r'\/', '_', endpoint)
        output = open('test/unit/asa/mock_data/{}.txt'.format(filename))

        f = None

        with requests_mock.mock() as m:
            m.get(full_url, text=output.read())
            f = requests.get(full_url)

        if returnObject:
            return f
        else:
            return f.text

    def test_connection(self):
        """ Test connection to ASA via the ASDM Interface"""
        response = self.get_resp(endpoint="/show+version", returnObject=True)

        if response.status_code is 200:
            return (True, 200)
        else:
            return (False, response.status_code)

        return response 
