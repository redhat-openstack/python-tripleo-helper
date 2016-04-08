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


expectation_start = [
    {'func': 'create_file', 'args': {
        'path': '/etc/sysconfig/network-scripts/ifcfg-eth1', 'content': '\nDEVICE="eth1"\nBOOTPROTO=static\nIPADDR=192.0.2.240\nNETMASK=255.255.255.0\nONBOOT=yes\nMTU=1400\n'}},
    {'func': 'run', 'args': {'cmd': 'ifup eth1'}}
]

expectation_load_instackenv = expectation_start
expectation_load_instackenv += [
    {'func': 'create_file', 'args': {'path': 'instackenv.json', 'content': '[]'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; openstack baremetal import --json instackenv.json'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; grep --count \'"cpu"\' instackenv.json'}, 'res': ('4\n', 0)},
    {'func': 'run', 'args': {'cmd': '. stackrc; ironic node-list|grep -c "power off"'}, 'res': ('4\n', 0)},
    {'func': 'run', 'args': {'cmd': '. stackrc; openstack baremetal configure boot'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; ironic node-list --fields uuid|awk \'/-.*-/ {print $2}\''}}]


@pytest.mark.parametrize('fake_sshclient', [expectation_load_instackenv], indirect=['fake_sshclient'])
def test_load_instackenv(ovb_undercloud):
    ovb_undercloud.load_instackenv()
