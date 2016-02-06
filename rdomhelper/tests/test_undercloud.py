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

import rdomhelper.undercloud


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

expectation_start_undercloud = [
    {'func': 'create_file', 'args': {
        'path': '/home/stack/guest_image.qcow2.md5',
        'content': 'acaf294494448266313343dec91ce91a /home/stack/guest_image.qcow2\n'
    }},
    {'func': 'run', 'args': {'cmd': 'md5sum -c /home/stack/guest_image.qcow2.md5'}},
    {'func': 'run', 'args': {'cmd': 'hostname -s'}},
    {'func': 'run', 'args': {'cmd': 'cat /etc/hostname'}, 'res': ('a.b', 0,)},
    {'func': 'run', 'args': {'cmd': "sed 's,127.0.0.1,127.0.0.1  a.b,' /etc/hosts"}},
    {'func': 'run', 'args': {'cmd': 'setenforce permissive'}},
    {'func': 'create_file', 'args': {
        'path': '/etc/sysconfig/selinux',
        'content': 'SELINUX=permissive\nSELINUXTYPE=targeted\n'
    }},
    {'func': 'run', 'args': {'cmd': 'repoquery --whatprovides /usr/share/instack-undercloud/puppet-stack-config/puppet-stack-config.pp'}, 'res': ('instack-undercloud-0:2.2.0-1.el7ost.noarch\n', 0,)},
    {'func': 'run', 'args': {'cmd': 'sed -i "s/.*Keystone_domain\\[\'heat_domain\'\\].*/Service\\[\'keystone\'\\] -> Class\\[\'::keystone::roles::admin\'\\] -> Class\\[\'::heat::keystone::domain\'\\]/" /usr/share/instack-undercloud/puppet-stack-config/puppet-stack-config.pp'}},
    {'func': 'run', 'args': {'cmd': 'rpm -qa openstack-ironic-api'}, 'res': ('openstack-ironic-api-4.2.2-3.el7ost.noarch\n', 0,)},
    {'func': 'run', 'args': {'cmd': 'systemctl start openstack-ironic-api.service'}},
    {'func': 'run', 'args': {'cmd': 'openstack undercloud install'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; heat stack-list'}},
]

expectation = [
    {'func': 'run', 'args': {
        'cmd': 'uname -a'}}] + expectation_start_undercloud


@pytest.mark.parametrize('fake_sshclient', [(expectation)], indirect=['fake_sshclient'])
def test_start_undercloud(fake_sshclient):
    test_undercloud = rdomhelper.undercloud.Undercloud(hostname='my-host')
    # TODO(Gonéri): manually create the connection 'stack' in the pool
    test_undercloud._ssh_pool.build_ssh_client(
        test_undercloud.hostname, 'stack', None, None)
    test_undercloud.start_undercloud(
        'http://host/guest_image_path.qcow2', 'acaf294494448266313343dec91ce91a')


expectation_start_overcloud = [
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
    {'func': 'run', 'args': {'cmd': '. stackrc; openstack overcloud image upload'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; openstack baremetal import --json instackenv.json'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; openstack baremetal configure boot'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; openstack flavor create --id auto --ram 4096 --disk 40 --vcpus 1 baremetal'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; openstack flavor set --property "cpu_arch"="x86_64" --property "capabilities:boot_option"="local" baremetal'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; for uuid in $(ironic node-list|awk \'/available/ {print $2}\'); do ironic node-update $uuid add properties/capabilities=profile:baremetal,boot_option:local; done'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; openstack overcloud deploy --debug ' +
                             '--templates ' +
                             '--log-file overcloud_deployment.log ' +
                             '--libvirt-type=qemu ' +
                             '--ntp-server north-america.pool.ntp.org ' +
                             '--control-scale 1 ' +
                             '--compute-scale 1 ' +
                             '--ceph-storage-scale 0 ' +
                             '--block-storage-scale 0 ' +
                             '--swift-storage-scale 0 ' +
                             '--control-flavor baremetal ' +
                             '--compute-flavor baremetal ' +
                             '--ceph-storage-flavor baremetal ' +
                             '--block-storage-flavor baremetal ' +
                             '--swift-storage-flavor baremetal'}},
    {'func': 'run', 'args': {'cmd': '. stackrc; test -f overcloudrc'}},

]

expectation = [
    {'func': 'run', 'args': {
        'cmd': 'uname -a'}}] + expectation_start_overcloud


@pytest.mark.parametrize('fake_sshclient', [(expectation)], indirect=['fake_sshclient'])
def test_start_overcloud(fake_sshclient):
    test_undercloud = rdomhelper.undercloud.Undercloud(hostname='my-host')
    # TODO(Gonéri): manually create the connection 'stack' in the pool
    test_undercloud._ssh_pool.build_ssh_client(
        test_undercloud.hostname, 'stack', None, None)
    test_undercloud.start_overcloud(files)


expectation_run_tempest = [
    {'func': 'run', 'args': {'cmd': '. overcloudrc; test -d tempest || mkdir tempest'}},
    {'func': 'run', 'args': {'cmd': 'yum install -y --quiet openstack-tempest-liberty'}},
    {'func': 'run', 'args': {'cmd': '. overcloudrc; cd tempest && /usr/share/openstack-tempest-liberty/tools/configure-tempest-directory'}},
    {'func': 'run', 'args': {'cmd': '. overcloudrc; neutron net-show ext-net || neutron net-create ext-net'}},
    {'func': 'run', 'args': {'cmd': '. overcloudrc; neutron subnet-show ext-subnet || neutron subnet-create ext-net --name ext-subnet   --allocation-pool start=172.16.23.40,end=172.16.23.50   --disable-dhcp --gateway 172.16.23.1 172.16.23.0/24'}},
    {'func': 'run', 'args': {'cmd': '. overcloudrc; neutron net-show ext-net -F id -f value'}, 'res': ('lets_pretend_is_an_id\n', 0,)},
    {'func': 'run', 'args': {'cmd': '. overcloudrc; cd tempest && tools/config_tempest.py --out etc/tempest.conf --network-id lets_pretend_is_an_id --deployer-input ~/tempest-deployer-input.conf --debug --create --image /home/stack/guest_image.qcow2 identity.uri $OS_AUTH_URL identity.admin_password $OS_PASSWORD network.tenant_network_cidr 192.168.0.0/24 object-storage.operator_role swiftoperator compute.image_ssh_user cloud-user compute.ssh_user cloud-user scenario.ssh_user cloud-user compute.flavor_ref 2 compute.flavor_ref_alt 2'}},
    {'func': 'run', 'args': {'cmd': '. overcloudrc; cd tempest && tools/run-tests.sh tempest'}},

]

expectation = [
    {'func': 'run', 'args': {
        'cmd': 'uname -a'}}] + expectation_run_tempest


@pytest.mark.parametrize('fake_sshclient', [(expectation)], indirect=['fake_sshclient'])
def test_run_tempest(fake_sshclient):
    test_undercloud = rdomhelper.undercloud.Undercloud(hostname='my-host')
    # TODO(Gonéri): manually create the connection 'stack' in the pool
    test_undercloud._ssh_pool.build_ssh_client(
        test_undercloud.hostname, 'stack', None, None)
    test_undercloud.run_tempest()
