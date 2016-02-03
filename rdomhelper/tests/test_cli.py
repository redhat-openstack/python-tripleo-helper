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

from rdomhelper import shell
import rdomhelper.undercloud

import rdomhelper.tests.test_host0
import rdomhelper.tests.test_server
import rdomhelper.tests.test_undercloud

expectation = [
    {'func': 'run', 'args': {'cmd': 'uname -a'}},
    {'func': 'run', 'args': {'cmd': 'subscription-manager repos \'--disable=*\' --enable=rhel-7-server-rpms'}},
    {'func': 'run', 'args': {'cmd': 'yum install -y --quiet https://kojipkgs.fedoraproject.org/packages/nosync/1.0/1.el7/x86_64/nosync-1.0-1.el7.x86_64.rpm'}},
    {'func': 'run', 'args': {'cmd': 'echo /usr/lib64/nosync/nosync.so > /etc/ld.so.preload'}}]

expectation += rdomhelper.tests.test_server.expectation_create_user
expectation += rdomhelper.tests.test_server.expectation_install_base_packages
expectation += rdomhelper.tests.test_server.expectation_clean_system
expectation += rdomhelper.tests.test_server.expectation_yum_update
expectation += rdomhelper.tests.test_server.expectation_install_osp
expectation += rdomhelper.tests.test_undercloud.expectation_start_undercloud
expectation += rdomhelper.tests.test_undercloud.expectation_start_overcloud


@pytest.mark.parametrize('fake_sshclient', [(expectation)], indirect=['fake_sshclient'])
def test_configure_undercloud(fake_sshclient):
    undercloud = rdomhelper.undercloud.Undercloud(hostname='192.168.1.1')
    repositories = [
        {'type': 'rhsm_channel', 'name': 'rhel-7-server-rpms'}
    ]
    files = {
        'overcloud-full': {
            'path': 'http://192.168.1.2/mburns/8.0/2015-12-03.1/images/overcloud-full.tar',
            'checksum': 'e88968c81703fbcf6dbc8623997f6a84'
        },
        'deploy-ramdisk-ironic': {
            'path': 'http://192.168.1.2/mburns/latest-8.0-images/deploy-ramdisk-ironic.tar',
            'checksum': '5c8fd42deb34831377f0bf69fbe71f4b'
        }
    }
    shell.configure_undercloud(undercloud, repositories, 'http://host/guest_image_path.qcow2', 'acaf294494448266313343dec91ce91a', files)
