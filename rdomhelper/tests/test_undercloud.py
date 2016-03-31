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

import rdomhelper.tests.test_server
import rdomhelper.undercloud

files = {
    'overcloud-full': {
        'image_path': 'http://192.168.1.2/mburns/8.0/2015-12-03.1/images/overcloud-full.tar',
        'checksum': 'e88968c81703fbcf6dbc8623997f6a84'
    },
    'deploy-ramdisk-ironic': {
        'image_path': 'http://192.168.1.2/mburns/latest-8.0-images/deploy-ramdisk-ironic.tar',
        'checksum': '5c8fd42deb34831377f0bf69fbe71f4b'
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
    {'func': 'run', 'args': {'cmd': 'yum install -y --quiet instack-undercloud'}},
    {'func': 'run', 'args': {'cmd': 'test ! -f /etc/os-net-config/config.json'}},
    {'func': 'run', 'args': {'cmd': 'sed -i \'s/"name": "br-ctlplane",/"name": "br-ctlplane",\\n      '
                             '"mtu": 1400,/\' '
                             '/usr/share/instack-undercloud/undercloud-stack-config/config.json.template'}},
    {'func': 'run', 'args': {'cmd': 'sed -i \'s/"primary": "true"/"primary": "true",\\n        "mtu": '
                             "1400/' "
                             '/usr/share/instack-undercloud/undercloud-stack-config/config.json.template'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_set_ctlplane_mtu], indirect=['fake_sshclient'])
def test_set_ctlplane_mtu(undercloud):
    undercloud.set_ctlplane_mtu(1400)


expectation_openstack_undercloud_install = [
    {'func': 'create_file', 'args': {
        'path': '/home/stack/guest_image.qcow2.md5',
        'content': 'acaf294494448266313343dec91ce91a /home/stack/guest_image.qcow2\n'
    }},
    {'func': 'run', 'args': {'cmd': 'md5sum -c /home/stack/guest_image.qcow2.md5'}},
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
    {'func': 'run', 'args': {'cmd': 'openstack undercloud install'}},
    {'func': 'run', 'args': {'cmd': 'rpm -qa openstack-ironic-api'}, 'res': ('openstack-ironic-api-4.2.2-3.el7ost.noarch\n', 0,)},
    {'func': 'run', 'args': {'cmd': 'systemctl start openstack-ironic-api.service'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; heat stack-list'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_openstack_undercloud_install], indirect=['fake_sshclient'])
def test_openstack_undercloud_install(undercloud):
    undercloud.openstack_undercloud_install(
        'http://host/guest_image_path.qcow2', 'acaf294494448266313343dec91ce91a')


expectation_configure = [
    {'func': 'run', 'args': {'cmd': ("subscription-manager repos "
                                     "'--disable=*' "
                                     "--enable=rhel-7-server-rpms "
                                     "--enable=rhel-7-server-optional-rpms "
                                     "--enable=rhel-7-server-extras-rpms")}},
    {'func': 'run', 'args': {'cmd': 'yum install -y --quiet bob'}},
    {'func': 'run', 'args': {'cmd': 'echo /usr/lib64/nosync/nosync.so > /etc/ld.so.preload'}}]

expectation_configure += rdomhelper.tests.test_server.expectation_create_user
expectation_configure += rdomhelper.tests.test_server.expectation_install_base_packages
expectation_configure += rdomhelper.tests.test_server.expectation_clean_system
expectation_configure += rdomhelper.tests.test_server.expectation_yum_update
expectation_configure += rdomhelper.tests.test_server.expectation_install_osp
expectation_configure += expectation_set_selinux
expectation_configure += expectation_fix_hostname


@pytest.mark.parametrize('fake_sshclient', [expectation_configure], indirect=['fake_sshclient'])
def test_configure(undercloud):
    undercloud.rhsm_active = True
    undercloud.nosync_rpm = 'bob'
    repositories = [
        {'type': 'rhsm_channel', 'name': 'rhel-7-server-rpms'}
    ]
    undercloud.configure(repositories)


expectation_fetch_overcloud_images = [
    {'func': 'create_file', 'args': {
        'path': '/home/stack/deploy-ramdisk-ironic.tar.md5',
        'content': '5c8fd42deb34831377f0bf69fbe71f4b /home/stack/deploy-ramdisk-ironic.tar\n'
    }},
    {'func': 'run', 'args': {'cmd': '. stackrc; md5sum -c /home/stack/deploy-ramdisk-ironic.tar.md5'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; tar xf /home/stack/deploy-ramdisk-ironic.tar'}},
    {'func': 'create_file', 'args': {
        'path': '/home/stack/overcloud-full.tar.md5',
        'content': 'e88968c81703fbcf6dbc8623997f6a84 /home/stack/overcloud-full.tar\n'
    }},
    {'func': 'run', 'args': {'cmd': '. stackrc; md5sum -c /home/stack/overcloud-full.tar.md5'}},
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
    {'func': 'run', 'args': {'cmd': '. stackrc; grep --count \'"cpu"\' instackenv.json'}, 'res': ('4\n', 0)},
    {'func': 'run', 'args': {'cmd': '. stackrc; ironic node-list|grep -c "power off"'}, 'res': ('4\n', 0)},
    {'func': 'run', 'args': {'cmd': '. stackrc; openstack baremetal configure boot'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_load_instackenv], indirect=['fake_sshclient'])
def test_load_instackenv(undercloud):
    undercloud.load_instackenv()


expectation_start_overcloud = [
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


expectation_run_tempest = [
    {'func': 'run', 'args': {'cmd': '. overcloudrc; test -d tempest || mkdir tempest'}},
    {'func': 'run', 'args': {'cmd': '. overcloudrc; yum install -y --quiet openstack-tempest-liberty'}},
    {'func': 'run', 'args': {'cmd': (
        '. overcloudrc; cd tempest && /usr/share/openstack-tempest-liberty/'
        'tools/configure-tempest-directory')}},
    {'func': 'run', 'args': {'cmd': (
        '. overcloudrc; neutron net-show ext-net '
        '|| neutron net-create ext-net')}},
    {'func': 'run', 'args': {'cmd': (
        '. overcloudrc; neutron subnet-show ext-subnet || neutron '
        'subnet-create ext-net --name ext-subnet   --allocation-pool '
        'start=172.16.23.40,end=172.16.23.50   --disable-dhcp '
        '--gateway 172.16.23.1 172.16.23.0/24')}},
    {'func': 'run', 'args': {
        'cmd': '. overcloudrc; neutron net-show ext-net -F id -f value'},
     'res': ('lets_pretend_is_an_id\n', 0,)},
    {'func': 'run', 'args': {'cmd': (
        '. overcloudrc; cd tempest && tools/config_tempest.py --out '
        'etc/tempest.conf --network-id lets_pretend_is_an_id '
        '--deployer-input ~/tempest-deployer-input.conf --debug --create '
        '--image /home/stack/guest_image.qcow2 identity.uri $OS_AUTH_URL '
        'identity.admin_password $OS_PASSWORD network.tenant_network_cidr '
        '192.168.0.0/24 object-storage.operator_role swiftoperator compute.'
        'image_ssh_user cloud-user compute.ssh_user cloud-user '
        'scenario.ssh_user cloud-user compute.flavor_ref 2 compute.flavor'
        '_ref_alt 2')}},
    {'func': 'run', 'args': {'cmd': (
        '. overcloudrc; cd '
        'tempest && tools/run-tests.sh tempest')}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_run_tempest], indirect=['fake_sshclient'])
def test_run_tempest(undercloud):
    undercloud.run_tempest()
