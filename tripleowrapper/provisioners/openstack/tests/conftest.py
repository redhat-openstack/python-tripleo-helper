# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Red Hat, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import mock
import pytest


@pytest.fixture
def nova_api():
    test_nova_api = mock.Mock()

    # Create mock resources
    mock_resource_1 = mock.Mock()
    mock_resource_1.name = 'resource_1'
    mock_resource_1.label = 'resource_1'
    mock_resource_1.id = 'f8a7cee0-b7c5-11e5-ae52-0021ccd9d101'

    mock_resource_2 = mock.Mock()
    mock_resource_2.name = 'resource_2'
    mock_resource_2.label = 'resource_2'
    mock_resource_2.id = '16a695de-b7c6-11e5-9c4c-0021ccd9d101'

    test_resources = [mock_resource_1, mock_resource_2]

    # Mock images
    test_nova_api.images = mock.Mock()
    test_nova_api.images.list.return_value = test_resources

    # Mock flavors
    test_nova_api.flavors = mock.Mock()
    test_nova_api.flavors.list.return_value = test_resources

    # Mock keypairs
    test_nova_api.keypairs = mock.Mock()
    test_nova_api.keypairs.list.return_value = test_resources

    # Mock networks
    test_nova_api.networks = mock.Mock()
    test_nova_api.networks.list.return_value = test_resources

    # Mock floating ips
    one_floating_ip = mock.Mock()
    one_floating_ip.ip = '46.231.123.123'
    one_floating_ip.instance_id = None
    one_floating_ip.fixed_ip = None

    test_nova_api.floating_ips = mock.Mock()
    test_nova_api.floating_ips.list.return_value = [one_floating_ip]

    return test_nova_api
