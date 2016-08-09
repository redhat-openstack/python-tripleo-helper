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


expectation_create_user = [
    {'func': 'run', 'args': {'cmd': 'adduser -m stack'}},
    {'func': 'create_file', 'args': {'path': '/etc/sudoers.d/stack', 'content': 'stack ALL=(root) NOPASSWD:ALL\n'}},
    {'func': 'run', 'args': {'cmd': 'mkdir -p /home/stack/.ssh'}},
    {'func': 'run', 'args': {'cmd': 'cp /root/.ssh/authorized_keys /home/stack/.ssh/authorized_keys'}},
    {'func': 'run', 'args': {'cmd': 'chown -R stack:stack /home/stack/.ssh'}},
    {'func': 'run', 'args': {'cmd': 'chmod 700 /home/stack/.ssh'}},
    {'func': 'run', 'args': {'cmd': 'chmod 600 /home/stack/.ssh/authorized_keys'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_create_user], indirect=['fake_sshclient'])
def test_create_user(server):
    server.create_stack_user()


expectation_rhsm_register = [
    {'func': 'run', 'args': {'cmd': 'rm /etc/pki/product/69.pem'}},
    {'func': 'run', 'args': {'cmd': 'subscription-manager register --username login --password password'}},
    {'func': 'run', 'args': {'cmd': 'subscription-manager attach --auto'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_rhsm_register], indirect=['fake_sshclient'])
def test_rhsm_register(server):
    server.rhsm_register(rhsm={'login': 'login', 'password': 'password'})


expectation_rhsm_register_with_pool_id = [
    {'func': 'run', 'args': {'cmd': 'rm /etc/pki/product/69.pem'}},
    {'func': 'run', 'args': {'cmd': 'subscription-manager register --username login --password password'}},
    {'func': 'run', 'args': {'cmd': 'subscription-manager attach --pool pool_id'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_rhsm_register_with_pool_id], indirect=['fake_sshclient'])
def test_rhsm_register_with_pool_id(server):
    server.rhsm_register(rhsm={'login': 'login', 'password': 'password', 'pool_id': 'pool_id'})


expectation_install_base_packages = [
    {'func': 'run', 'args': {
        'cmd': 'yum install -y --quiet yum-utils iptables libselinux-python psmisc redhat-lsb-core rsync libguestfs-tools'}}]


@pytest.mark.parametrize('fake_sshclient', [expectation_install_base_packages], indirect=['fake_sshclient'])
def test_install_base_packages(server):
    server.install_base_packages()

expectation_clean_system = [
    {'func': 'run', 'args': {'cmd': 'systemctl disable NetworkManager'}},
    {'func': 'run', 'args': {'cmd': 'systemctl stop NetworkManager'}},
    {'func': 'run', 'args': {'cmd': 'pkill -9 dhclient'}},
    {'func': 'run', 'args': {'cmd': 'yum remove -y --quiet cloud-init NetworkManager'}},
    {'func': 'run', 'args': {'cmd': 'systemctl enable network'}},
    {'func': 'run', 'args': {'cmd': 'systemctl restart network'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_clean_system], indirect=['fake_sshclient'])
def test_clean_system(server):
    server.clean_system()

expectation_yum_update = [
    {'func': 'run', 'args': {'cmd': 'yum update -y --quiet'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_yum_update], indirect=['fake_sshclient'])
def test_yum_update(server):
    server.yum_update()


expectation_yum_update_with_reboot = [
    {'func': 'run', 'args': {'cmd': 'yum update -y --quiet'}},
    {'func': 'run', 'args': {'cmd': 'find /boot/ -anewer /proc/1/stat -name "initramfs*" -exec reboot \;'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_yum_update_with_reboot], indirect=['fake_sshclient'])
def test_yum_update_with_reboot(server):
    server.yum_update(allow_reboot=True)


expectation_install_osp = [
    {'func': 'run', 'args': {'cmd': 'yum install -y --quiet yum-plugin-priorities python-tripleoclient python-rdomanager-oscplugin'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_install_osp], indirect=['fake_sshclient'])
def test_install_osp(server):
    server.install_osp()


expectation_enable_user_needed_rhel = [
    # First case, we need to adjust root's authorized_keys file
    {'func': 'run', 'args': {'cmd': 'uname -a'}, 'res': ('Please login as the user "cloud-user"', 0)},
    {'func': 'run', 'args': {'cmd': 'sudo sed -i \'s,.*ssh-rsa,ssh-rsa,\' /root/.ssh/authorized_keys'}}
]
expectation_enable_user_needed_fedora = [
    # First case, we need to adjust root's authorized_keys file
    {'func': 'run', 'args': {'cmd': 'uname -a'}, 'res': ('Please login as the user "fedora" rather than the user "root"', 0)},
    {'func': 'run', 'args': {'cmd': 'sudo sed -i \'s,.*ssh-rsa,ssh-rsa,\' /root/.ssh/authorized_keys'}}
]
expectation_enable_user_useless = [
    # second case, we can directly call uname, the root use is enabled
    {'func': 'run', 'args': {'cmd': 'uname -a'}, 'res': ('Linux demo 4.3.4-300.fc23.x86_64+debug #1 SMP Mon Jan 25 13:22:34 UTC 2016 x86_64 x86_64 x86_64 GNU/Linux', 0)},
]


@pytest.mark.parametrize('fake_sshclient', [
    expectation_enable_user_needed_rhel,
    expectation_enable_user_needed_fedora,
    expectation_enable_user_useless], indirect=['fake_sshclient'])
def test_enable_user(server_without_root_enabled):
    server_without_root_enabled.enable_user('root')

expectation_fetch_image = [
    {'func': 'create_file', 'args': {'path': 'somewhere.md5', 'content': 'this_is_a_Bad_md5 somewhere\n'}},
    {'func': 'run', 'args': {'cmd': 'md5sum -c somewhere.md5'}, 'res': ('md5sum: somewhere: no properly formatted MD5 checksum lines found', 1)},
    {'func': 'run', 'args': {'cmd': 'curl -s -o somewhere http://host/image'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_fetch_image], indirect=['fake_sshclient'])
def test_fetch_image(server):
    server.fetch_image('http://host/image', 'somewhere', 'this_is_a_Bad_md5')
