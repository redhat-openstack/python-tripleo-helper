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

from rdomhelper import server
from rdomhelper.tests.commands import server as server_cmds
from rdomhelper.tests import server_mock_methods as s_m

import mock


@mock.patch("rdomhelper.server.ssh.PoolSshClient")
@mock.patch("rdomhelper.server.ssh.SshClient")
def test_create_user(mock_pool_ssh, mock_ssh_client):
    test_server = server.Server('toto', 'titi')

    test_server.run = s_m.MockServerRun()
    test_server.create_file = s_m.MockServerCreateFile()
    test_server.create_stack_user()

    assert server_cmds.CREATE_STACK_USER_RUN == test_server.run.call_list()
    assert server_cmds.CREATE_STACK_USER_CREATE_FILE == test_server.create_file.call_list()


@mock.patch("rdomhelper.server.ssh.PoolSshClient")
@mock.patch("rdomhelper.server.ssh.SshClient")
def test_rhsm_register(mock_pool_ssh, mock_ssh_client):
    test_server = server.Server('toto', 'titi')
    test_server.run = s_m.MockServerRun()

    test_server.rhsm_register('login', 'pass')
    assert server_cmds.RHSM_REGISTER == test_server.run.call_list()

    test_server.run.clear()
    test_server.rhsm_register('login', 'pass', 'pool_id')
    assert server_cmds.RHSM_REGISTER_POOL_ID == test_server.run.call_list()
