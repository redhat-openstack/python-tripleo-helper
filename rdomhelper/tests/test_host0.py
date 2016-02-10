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

import rdomhelper.host0

expectation_build_undercloud = [
    {'func': 'run', 'args': {
        'cmd': 'uname -a'}},
    {'func': 'run', 'args': {
        'cmd': 'sysctl net.ipv4.ip_forward=1'}},
    {'func': 'create_file', 'args': {
        'path': '/home/stack/guest_image.qcow2.md5',
        'content': 'f982ce8e27bc8222a0c1f0e769a31de1 /home/stack/guest_image.qcow2\n'}},
    {'func': 'run', 'args': {'cmd': 'md5sum -c /home/stack/guest_image.qcow2.md5'}},
    {'func': 'run', 'args': {'cmd': 'LIBGUESTFS_BACKEND=direct virt-customize -a /home/stack/guest_image.qcow2 --run-command \'echo MTU="1400" >> /etc/sysconfig/network-scripts/ifcfg-eth0\''}},
    {'func': 'run', 'args': {'cmd': 'mkdir -p /home/stack/DIB'}},
    {'func': 'run', 'args': {'cmd': 'cp -v /etc/yum.repos.d/*.repo /home/stack/DIB'}},
    {'func': 'run', 'args': {'cmd': 'find /home/stack/DIB -type f'}, 'res': ('/home/stack/DIB/rhos-release-8-director.repo\n/home/stack/DIB/rhos-release-8.repo\n/home/stack/DIB/redhat.repo\n', 0)},
    {'func': 'create_file', 'args': {
        'path': 'virt-setup-env',
        'content': 'export PATH=\'/usr/local/bin:/bin:/usr/bin:/usr/local/sbin:/usr/sbin:/home/stack/bin\'\n\nexport DIB_LOCAL_IMAGE=/home/stack/guest_image.qcow2\nexport DIB_YUM_REPO_CONF="/home/stack/DIB/rhos-release-8-director.repo /home/stack/DIB/rhos-release-8.repo /home/stack/DIB/redhat.repo"\nexport USE_DELOREAN_TRUNK=0\nexport RHOS=1\nexport NODE_DIST=rhel7\n\n\nexport NODE_DIST=rhel7\nexport REG_METHOD=portal\nexport REG_USER="None"\nexport REG_PASSWORD="None"\nexport REG_POOL_ID=""\nexport REG_REPOS="rhel-7-server-rpms rhel-7-server-extras-rpms rhel-ha-for-rhel-7-server-rpms rhel-7-server-optional-rpms rhel-7-server-openstack-7.0-rpms"\n\n\nexport NODE_COUNT=2\n\n\nexport NODE_MEM=6144\n\n\n\nexport NODE_CPU=2\n\n\n\nexport UNDERCLOUD_NODE_MEM=8192\n'}},
    {'func': 'run', 'args': {'cmd': 'virsh destroy instack'}},
    {'func': 'run', 'args': {'cmd': 'virsh undefine instack --remove-all-storage'}},
    {'func': 'run', 'args': {'cmd': 'source virt-setup-env; instack-virt-setup'}},
    {'func': 'run',
     'args': {
         'cmd': "/sbin/ip n | grep $(tripleo get-vm-mac instack) | awk '{print $1;}'"},
     'res': ('192.168.122.234', 0,)},
    {'func': 'run', 'args': {
        'cmd': 'uname -a'},
     'hostname': '192.168.122.234'},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_build_undercloud], indirect=['fake_sshclient'])
def test_build_undercloud_on_libvirt(fake_sshclient):
    test_host0 = rdomhelper.host0.Host0(hostname='my-host')

    # TODO(Gonéri): manually create the connection 'stack' in the pool
    test_host0._ssh_pool.build_ssh_client(
        test_host0.hostname, 'stack', None, None)

    undercloud = test_host0.build_undercloud_on_libvirt(
        'http://host/guest_image_path.qcow2', 'f982ce8e27bc8222a0c1f0e769a31de1')

    assert undercloud
    assert undercloud.hostname == '192.168.122.234'


expectation_deploy_hypervisor = [
    {'func': 'run', 'args': {'cmd': 'uname -a'}},
    {'func': 'run', 'args': {'cmd': 'yum install -y --quiet libvirt-daemon-driver-nwfilter libvirt-client libvirt-daemon-config-network libvirt-daemon-driver-nodedev libvirt-daemon-kvm libvirt-python libvirt-daemon-config-nwfilter libvirt-glib libvirt-daemon libvirt-daemon-driver-storage libvirt libvirt-daemon-driver-network libvirt-devel libvirt-gobject libvirt-daemon-driver-secret libvirt-daemon-driver-qemu libvirt-daemon-driver-interface libguestfs-tools.noarch virt-install genisoimage openstack-tripleo libguestfs-tools instack-undercloud'}},
    {'func': 'run', 'args': {'cmd': 'sed -i "s,#auth_unix_rw,auth_unix_rw," /etc/libvirt/libvirtd.conf'}},
    {'func': 'run', 'args': {'cmd': 'systemctl start libvirtd'}},
    {'func': 'run', 'args': {'cmd': 'systemctl status libvirtd'}},
    {'func': 'run', 'args': {'cmd': 'yum install -y --quiet yum-utils iptables libselinux-python psmisc redhat-lsb-core rsync'}},
    {'func': 'run', 'args': {'cmd': 'systemctl disable NetworkManager'}},
    {'func': 'run', 'args': {'cmd': 'systemctl stop NetworkManager'}},
    {'func': 'run', 'args': {'cmd': 'pkill -9 dhclient'}},
    {'func': 'run', 'args': {'cmd': 'yum remove -y --quiet cloud-init NetworkManager'}},
    {'func': 'run', 'args': {'cmd': 'systemctl enable network'}},
    {'func': 'run', 'args': {'cmd': 'systemctl restart network'}},
    {'func': 'run', 'args': {'cmd': 'yum update -y'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_deploy_hypervisor], indirect=['fake_sshclient'])
def test_deploy_hypervisor(fake_sshclient):
    test_host0 = rdomhelper.host0.Host0(hostname='my-host')
    test_host0.deploy_hypervisor()
