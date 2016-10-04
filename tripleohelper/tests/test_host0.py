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


expectation_build_undercloud = [
    {'func': 'run', 'args': {
        'cmd': 'sysctl net.ipv4.ip_forward=1'}},
    {'func': 'run', 'args': {
        'cmd': 'curl -s -o /home/stack/guest_image.qcow2 http://host/guest_image_path.qcow2'}},
    {'func': 'run', 'args': {'cmd': 'LIBGUESTFS_BACKEND=direct virt-customize -a /home/stack/guest_image.qcow2 --run-command \'echo MTU="1400" >> /etc/sysconfig/network-scripts/ifcfg-eth0\''}},
    {'func': 'run', 'args': {'cmd': 'mkdir -p /home/stack/DIB'}},
    {'func': 'run', 'args': {'cmd': 'cp -v /etc/yum.repos.d/*.repo /home/stack/DIB'}},
    {'func': 'run', 'args': {'cmd': 'find /home/stack/DIB -type f'}, 'res': ('/home/stack/DIB/rhos-release-8-director.repo\n/home/stack/DIB/rhos-release-8.repo\n/home/stack/DIB/redhat.repo\n', 0)},
    {'func': 'create_file', 'args': {
        'path': 'virt-setup-env',
        'content': 'export PATH=\'/usr/local/bin:/bin:/usr/bin:/usr/local/sbin:/usr/sbin:/home/stack/bin\'\n\nexport DIB_LOCAL_IMAGE=/home/stack/guest_image.qcow2\nexport DIB_YUM_REPO_CONF="/home/stack/DIB/rhos-release-8-director.repo /home/stack/DIB/rhos-release-8.repo /home/stack/DIB/redhat.repo"\nexport USE_DELOREAN_TRUNK=0\nexport RHOS=1\nexport NODE_DIST=rhel7\n\n\nexport NODE_DIST=rhel7\nexport REG_METHOD=portal\nexport REG_USER="user"\nexport REG_PASSWORD="password"\nexport REG_POOL_ID=""\nexport REG_REPOS="rhel-7-server-rpms rhel-7-server-optional-rpms rhel-7-server-extras-rpms"\n\n\nexport NODE_COUNT=2\n\n\nexport NODE_MEM=6144\n\n\n\nexport NODE_CPU=2\n\n\n\nexport UNDERCLOUD_NODE_MEM=8192\n'}},
    {'func': 'run', 'args': {'cmd': 'virsh destroy instack'}},
    {'func': 'run', 'args': {'cmd': 'virsh undefine instack --remove-all-storage'}},
    {'func': 'run', 'args': {'cmd': 'source virt-setup-env; instack-virt-setup'}},
    {'func': 'run',
     'args': {
         'cmd': "/sbin/ip n | grep $(tripleo get-vm-mac instack) | awk '{print $1;}'"},
     'res': ('192.168.122.234', 0,)},
]


repositores = [
    {'type': 'rhsm_channel', 'name': 'rhel-7-server-rpms'},
    {'type': 'rhsm_channel', 'name': 'rhel-7-server-optional-rpms'},
    {'type': 'rhsm_channel', 'name': 'rhel-7-server-extras-rpms'}]


@pytest.mark.parametrize('fake_sshclient', [expectation_build_undercloud], indirect=['fake_sshclient'])
def test_build_undercloud_on_libvirt(host0):
    undercloud = host0.build_undercloud_on_libvirt(
        'http://host/guest_image_path.qcow2',
        rhsm={'login': 'user', 'password': 'password'},
        repositories=repositores)
    assert undercloud
    assert undercloud.hostname == '192.168.122.234'


expectation_deploy_hypervisor = [
    {'func': 'run', 'args': {'cmd': 'yum install -y --quiet libvirt-daemon-driver-nwfilter libvirt-client libvirt-daemon-config-network libvirt-daemon-driver-nodedev libvirt-daemon-kvm libvirt-python libvirt-daemon-config-nwfilter libvirt-glib libvirt-daemon libvirt-daemon-driver-storage libvirt libvirt-daemon-driver-network libvirt-devel libvirt-gobject libvirt-daemon-driver-secret libvirt-daemon-driver-qemu libvirt-daemon-driver-interface libguestfs-tools virt-install genisoimage openstack-tripleo instack-undercloud'}},
    {'func': 'run', 'args': {'cmd': 'sed -i "s,#auth_unix_rw,auth_unix_rw," /etc/libvirt/libvirtd.conf'}},
    {'func': 'run', 'args': {'cmd': 'systemctl start libvirtd'}},
    {'func': 'run', 'args': {'cmd': 'systemctl status libvirtd'}},
    {'func': 'run', 'args': {'cmd': 'yum install -y --quiet yum-utils iptables libselinux-python psmisc redhat-lsb-core rsync libguestfs-tools'}},
    {'func': 'run', 'args': {'cmd': 'systemctl disable NetworkManager'}},
    {'func': 'run', 'args': {'cmd': 'systemctl stop NetworkManager'}},
    {'func': 'run', 'args': {'cmd': 'pkill -9 dhclient'}},
    {'func': 'run', 'args': {'cmd': 'yum remove -y --quiet cloud-init NetworkManager'}},
    {'func': 'run', 'args': {'cmd': 'systemctl enable network'}},
    {'func': 'run', 'args': {'cmd': 'systemctl restart network'}},
    {'func': 'run', 'args': {'cmd': 'yum clean all'}},
    {'func': 'run', 'args': {'cmd': 'subscription-manager repos --list-enabled'}},
    {'func': 'run', 'args': {'cmd': 'yum repolist'}},
    {'func': 'run', 'args': {'cmd': 'yum update -y --quiet'}},
]


@pytest.mark.parametrize('fake_sshclient', [expectation_deploy_hypervisor], indirect=['fake_sshclient'])
def test_deploy_hypervisor(host0):
    host0.deploy_hypervisor()
