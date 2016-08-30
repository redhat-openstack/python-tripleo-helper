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

from tripleohelper.provisioners.openstack import utils

import mock
from novaclient import client as nova_client


def test_get_image_id(nova_api):
    image_id_1 = utils.get_image_id(nova_api, 'resource_1')
    assert image_id_1 == "f8a7cee0-b7c5-11e5-ae52-0021ccd9d101"
    image_id_2 = utils.get_image_id(nova_api, 'resource_2')
    assert image_id_2 == "16a695de-b7c6-11e5-9c4c-0021ccd9d101"
    image_id = utils.get_image_id(nova_api, 'not_available')
    assert None == image_id


def test_get_flavor_id(nova_api):
    flavor_id_1 = utils.get_flavor_id(nova_api, 'resource_1')
    assert flavor_id_1 == "f8a7cee0-b7c5-11e5-ae52-0021ccd9d101"
    flavor_id_2 = utils.get_flavor_id(nova_api, 'resource_2')
    assert flavor_id_2 == "16a695de-b7c6-11e5-9c4c-0021ccd9d101"
    flavor_id = utils.get_flavor_id(nova_api, 'not_available')
    assert None == flavor_id


def test_get_keypair_id(nova_api):
    keypair_id_1 = utils.get_keypair_id(nova_api, 'resource_1')
    assert keypair_id_1 == "f8a7cee0-b7c5-11e5-ae52-0021ccd9d101"
    keypair_id_2 = utils.get_keypair_id(nova_api, 'resource_2')
    assert keypair_id_2 == "16a695de-b7c6-11e5-9c4c-0021ccd9d101"
    keypair_id = utils.get_keypair_id(nova_api, 'not_available')
    assert None == keypair_id


def test_get_network_id(nova_api):
    keypair_id_1 = utils.get_network_id(nova_api, 'resource_1')
    assert keypair_id_1 == "f8a7cee0-b7c5-11e5-ae52-0021ccd9d101"
    keypair_id_2 = utils.get_network_id(nova_api, 'resource_2')
    assert keypair_id_2 == "16a695de-b7c6-11e5-9c4c-0021ccd9d101"
    network_id = utils.get_network_id(nova_api, 'not_available')
    assert None == network_id


@mock.patch('novaclient.client.Client', spec=nova_client.Client)
def test_build_nova_api(mock_nova_client):
    sess = utils.ks_session('http://auth_url', 'username', 'password', 'tenant')
    utils.build_nova_api(sess)
    mock_nova_client.assert_called_with(2, session=sess)


def test_get_floating_ip(nova_api):
    assert utils.get_floating_ip(nova_api) is not None

    nova_api.floating_ips.list()[0].instance_id = "instance_id"
    assert utils.get_floating_ip(nova_api) is None

    nova_api.floating_ips.list()[0].instance_id = None
    nova_api.floating_ips.list()[0].fixed_ip = "fixed_ip"
    assert utils.get_floating_ip(nova_api) is None


def test_add_a_floating_ip(nova_api):
    mock_instance = mock.Mock()
    mock_instance.add_floating_ip = mock.Mock()
    ip = utils.add_a_floating_ip(nova_api, mock_instance)
    mock_instance.add_floating_ip.assert_called_with('46.231.123.123')
    assert ip == '46.231.123.123'


def test_add_security_groups():
    test_instance = mock.Mock()
    test_instance.add_security_group = mock.Mock()
    test_sgs = [mock.Mock(), mock.Mock()]
    utils.add_security_groups(test_instance, test_sgs)

    test_instance.add_security_group.assert_called_with(test_sgs[1])
    assert test_instance.add_security_group.call_count == 2


def test_remove_instances_by_prefix(nova_api):
    test_server_1, test_server_2 = nova_api.servers.list()
    utils.remove_instances_by_prefix(nova_api, 'resource_1')
    test_server_1.delete.assert_called_with()
    test_server_2.delete.assert_not_called()
