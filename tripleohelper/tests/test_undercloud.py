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

import tripleohelper.tests.test_server
import tripleohelper.undercloud

files = {
    'overcloud-full': {
        'image_path': 'http://192.168.1.2/mburns/8.0/2015-12-03.1/images/overcloud-full.tar',
    },
    'deploy-ramdisk-ironic': {
        'image_path': 'http://192.168.1.2/mburns/latest-8.0-images/deploy-ramdisk-ironic.tar',
    }
}

expectation_set_selinux = [
    {'func': 'run', 'args': {'cmd': 'setenforce permissive'}},
    {'func': 'create_file', 'args': {
        'path': '/etc/sysconfig/selinux',
        'content': 'SELINUX=permissive\nSELINUXTYPE=targeted\n'
    }},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_set_selinux], indirect=['fake_sshclient'])
def test_set_selinux(undercloud):
    undercloud.set_selinux('permissive')


expectation_fix_hostname = [
    {'func': 'run', 'args': {'cmd': 'hostname'}, 'res': ('hostname.localdomain\n', 0)},
    {'func': 'run', 'args': {'cmd': 'hostname -s'}, 'res': ('hostname\n', 0)},
    {'func': 'run', 'args': {'cmd': 'cat /etc/hostname'}, 'res': ('a.b\n', 0,)},
    {'func': 'run', 'args': {'cmd': "sed -i 's,127.0.0.1,127.0.0.1 hostname a.b hostname.localdomain undercloud.openstacklocal,' /etc/hosts"}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_fix_hostname], indirect=['fake_sshclient'])
def test_fix_hostname(undercloud):
    undercloud.fix_hostname()


expectation_set_ctlplane_mtu = [
    {'func': 'run', 'args': {'cmd': 'find /etc/sysconfig/network-scripts -name "ifcfg-eth?" -exec sed -i \'$ iMTU="1400"\' {} \\;'}},
    {'func': 'run', 'args': {'cmd': 'systemctl restart network'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_set_ctlplane_mtu], indirect=['fake_sshclient'])
def test_set_ctlplane_mtu(undercloud):
    undercloud.set_ctlplane_mtu(1400)


expectation_openstack_undercloud_install = [
    {'func': 'run', 'args': {'cmd': (
        'repoquery --whatprovides /usr/share/instack-undercloud/'
        'puppet-stack-config/puppet-stack-config.pp')
    }, 'res': ('instack-undercloud-0:2.2.0-1.el7ost.noarch\n', 0,)},
    {'func': 'run', 'args': {'cmd': (
        'sed -i "s/.*Keystone_domain\\[\'heat_domain\'\\].*/Service\\'
        '[\'keystone\'\\] -> Class\\[\'::keystone::roles::admin\'\\] '
        '-> Class\\[\'::heat::keystone::domain\'\\]/" '
        '/usr/share/instack-undercloud/puppet-stack-config/'
        'puppet-stack-config.pp')}},
    {'func': 'run', 'args': {'cmd': 'OS_PASSWORD=bob openstack undercloud install'}},
    {'func': 'run', 'args': {'cmd': 'rpm -qa openstack-ironic-api'}, 'res': ('openstack-ironic-api-4.2.2-3.el7ost.noarch\n', 0,)},
    {'func': 'run', 'args': {'cmd': 'systemctl start openstack-ironic-api.service'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; heat stack-list'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_openstack_undercloud_install], indirect=['fake_sshclient'])
def test_openstack_undercloud_install(undercloud):
    undercloud.openstack_undercloud_install()


expectation_configure = [
    {'func': 'run', 'args': {'cmd': ("subscription-manager repos "
                                     "'--disable=*' "
                                     "--enable=rhel-7-server-rpms "
                                     "--enable=rhel-7-server-optional-rpms "
                                     "--enable=rhel-7-server-extras-rpms")}}]

expectation_configure += tripleohelper.tests.test_server.expectation_create_user
expectation_configure += tripleohelper.tests.test_server.expectation_install_base_packages
expectation_configure += tripleohelper.tests.test_server.expectation_clean_system
expectation_configure += tripleohelper.tests.test_server.expectation_yum_update_with_reboot
expectation_configure += [{'func': 'run', 'args': {'cmd': 'uname -a'}}]
expectation_configure += tripleohelper.tests.test_server.expectation_install_osp
expectation_configure += expectation_set_selinux
expectation_configure += expectation_fix_hostname


@pytest.mark.parametrize('fake_sshclient', [expectation_configure], indirect=['fake_sshclient'])
def test_configure(undercloud):
    undercloud.rhsm_active = True
    repositories = [
        {'type': 'rhsm_channel', 'name': 'rhel-7-server-rpms'}
    ]
    undercloud.configure(repositories)


expectation_fetch_overcloud_images = [
    {'func': 'run', 'args': {'cmd': '. stackrc; test -f /home/stack/deploy-ramdisk-ironic.tar || curl -L -s -o /home/stack/deploy-ramdisk-ironic.tar http://192.168.1.2/mburns/latest-8.0-images/deploy-ramdisk-ironic.tar'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; tar xf /home/stack/deploy-ramdisk-ironic.tar'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; test -f /home/stack/overcloud-full.tar || curl -L -s -o /home/stack/overcloud-full.tar http://192.168.1.2/mburns/8.0/2015-12-03.1/images/overcloud-full.tar'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; tar xf /home/stack/overcloud-full.tar'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_fetch_overcloud_images], indirect=['fake_sshclient'])
def test_fetch_overcloud_images(undercloud):
    undercloud.add_environment_file(user='stack', filename='stackrc')
    undercloud.fetch_overcloud_images(files)


expectation_overcloud_load_image = [
    {'func': 'run', 'args': {'cmd': '. stackrc; openstack overcloud image upload'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_overcloud_load_image], indirect=['fake_sshclient'])
def test_overcloud_image_upload(undercloud):
    undercloud.add_environment_file(user='stack', filename='stackrc')
    undercloud.overcloud_image_upload()


expectation_load_instackenv = [
    {'func': 'run', 'args': {'cmd': '. stackrc; openstack baremetal import --json instackenv.json'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; jq -M ".nodes|length" /home/stack/instackenv.json'}, 'res': ('0\n', 0)},
    {'func': 'run', 'args': {'cmd': '. stackrc; jq -M ".|length" /home/stack/instackenv.json'}, 'res': ('4\n', 0)},
    {'func': 'run', 'args': {'cmd': '. stackrc; ironic node-list|grep -c "power off"'}, 'res': ('4\n', 0)},
    {'func': 'run', 'args': {'cmd': ". stackrc; ironic node-list --fields uuid|awk '/-.*-/ {print $2}'"}},
    {'func': 'run', 'args': {'cmd': '. stackrc; openstack baremetal configure boot'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_load_instackenv], indirect=['fake_sshclient'])
def test_load_instackenv(undercloud):
    undercloud.load_instackenv()


expectation_start_overcloud = [
    {'func': 'run', 'args': {'cmd': 'yum install -y --quiet ipmitool'}},
    {'func': 'run', 'args': {'cmd': 'ipmitool -I lanplus -H neverland -U root -P pw chassis power off'}},
    {'func': 'run', 'args': {'cmd': (
        '. stackrc; openstack overcloud deploy '
        '--templates '
        '--log-file overcloud_deployment.log '
        '--ntp-server north-america.pool.ntp.org '
        '--control-scale 1 '
        '--compute-scale 1 '
        '--ceph-storage-scale 0 '
        '--block-storage-scale 0 '
        '--swift-storage-scale 0 '
        '--control-flavor baremetal '
        '--compute-flavor baremetal '
        '--ceph-storage-flavor baremetal '
        '--block-storage-flavor baremetal '
        '--swift-storage-flavor baremetal ')}},
    {'func': 'run', 'args': {'cmd': '. stackrc; test -f overcloudrc'}}]


@pytest.mark.parametrize('fake_sshclient', [expectation_start_overcloud], indirect=['fake_sshclient'])
def test_start_overcloud_deploy(undercloud):
    undercloud.start_overcloud_deploy(control_scale=1, compute_scale=1)


expectation_nova_version = [
    {'func': 'run', 'args': {'cmd': 'nova-manage --version'}, 'res': ('14.0.4\n', 0)},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_nova_version], indirect=['fake_sshclient'])
def test_nova_version(undercloud):
    undercloud.nova_version()
