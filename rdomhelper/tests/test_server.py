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

import pytest

from rdomhelper import server


expectation = [
    {'func': 'run', 'args': {'cmd': 'sudo sed -i \'s,.*ssh-rsa,ssh-rsa,\' /root/.ssh/authorized_keys'}},
    {'func': 'run', 'args': {'cmd': 'adduser -m stack'}},
    {'func': 'create_file', 'args': {'path': '/etc/sudoers.d/stack', 'content': 'stack ALL=(root) NOPASSWD:ALL\n'}},
    {'func': 'run', 'args': {'cmd': 'mkdir -p /home/stack/.ssh'}},
    {'func': 'run', 'args': {'cmd': 'cp /root/.ssh/authorized_keys /home/stack/.ssh/authorized_keys'}},
    {'func': 'run', 'args': {'cmd': 'chown -R stack:stack /home/stack/.ssh'}},
    {'func': 'run', 'args': {'cmd': 'chmod 700 /home/stack/.ssh'}},
    {'func': 'run', 'args': {'cmd': 'chmod 600 /home/stack/.ssh/authorized_keys'}},
]


@pytest.mark.parametrize('fake_sshclient', [(expectation)], indirect=['fake_sshclient'])
def test_create_user(fake_sshclient):
    test_server = server.Server('toto', 'titi')
    test_server.create_stack_user()


expectation = [
    {'func': 'run', 'args': {'cmd': 'sudo sed -i \'s,.*ssh-rsa,ssh-rsa,\' /root/.ssh/authorized_keys'}},
    {'func': 'run', 'args': {'cmd': 'rm /etc/pki/product/69.pem'}},
    {'func': 'run', 'args': {'cmd': 'subscription-manager register --username login --password pass'}},
    {'func': 'run', 'args': {'cmd': 'subscription-manager attach --auto'}},
]


@pytest.mark.parametrize('fake_sshclient', [(expectation)], indirect=['fake_sshclient'])
def test_rhsm_register(fake_sshclient):
    test_server = server.Server('toto', 'titi')
    test_server.rhsm_register('login', 'pass')

expectation = [
    {'func': 'run', 'args': {'cmd': 'sudo sed -i \'s,.*ssh-rsa,ssh-rsa,\' /root/.ssh/authorized_keys'}},
    {'func': 'run', 'args': {'cmd': 'rm /etc/pki/product/69.pem'}},
    {'func': 'run', 'args': {'cmd': 'subscription-manager register --username login --password pass'}},
    {'func': 'run', 'args': {'cmd': 'subscription-manager attach --pool pool_id'}},
]


@pytest.mark.parametrize('fake_sshclient', [(expectation)], indirect=['fake_sshclient'])
def test_rhsm_register_with_pool_id(fake_sshclient):
    test_server = server.Server('toto', 'titi')
    test_server.rhsm_register('login', 'pass', 'pool_id')
