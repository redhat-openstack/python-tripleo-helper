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

from rdomhelper.server import Server
from rdomhelper.undercloud import Undercloud

from jinja2 import Environment
from jinja2 import FileSystemLoader


class Host0(Server):
    def __init__(self, **kwargs):
        Server.__init__(self, **kwargs)

    def deploy_hypervisor(self):
        self.yum_install(['libvirt-daemon-driver-nwfilter', 'libvirt-client', 'libvirt-daemon-config-network', 'libvirt-daemon-driver-nodedev', 'libvirt-daemon-kvm', 'libvirt-python', 'libvirt-daemon-config-nwfilter', 'libvirt-glib', 'libvirt-daemon', 'libvirt-daemon-driver-storage', 'libvirt', 'libvirt-daemon-driver-network', 'libvirt-devel', 'libvirt-gobject', 'libvirt-daemon-driver-secret', 'libvirt-daemon-driver-qemu', 'libvirt-daemon-driver-interface', 'libguestfs-tools.noarch', 'virt-install', 'genisoimage', 'openstack-tripleo', 'libguestfs-tools', 'instack-undercloud'])
        self.run('sed -i "s,#auth_unix_rw,auth_unix_rw," /etc/libvirt/libvirtd.conf')
        self.run('systemctl start libvirtd')
        self.run('systemctl status libvirtd')

        self.install_base_packages()
        self.clean_system()
        self.yum_update()

    def instack_virt_setup(self, guest_image_path, guest_image_checksum,
                           rhsm_login=None, rhsm_password=None):

        self.run('sysctl net.ipv4.ip_forward=1')
        self.fetch_image(path=guest_image_path, checksum=guest_image_checksum, dest='/home/stack/guest_image.qcow2',
                         user='stack')
        # NOTE(Gonéri): this is a hack for our OpenStack, the MTU of its outgoing route
        # is 1400 and libvirt do not provide a mechanism to adjust the guests MTU.
        self.run("LIBGUESTFS_BACKEND=direct virt-customize -a /home/stack/guest_image.qcow2 --run-command 'echo MTU=\"1400\" >> /etc/sysconfig/network-scripts/ifcfg-eth0'")

        env = Environment()
        env.loader = FileSystemLoader('templates')
        template = env.get_template('virt-setup-env.j2')
        self.run('mkdir -p /home/stack/DIB', user='stack')
        self.run('cp -v /etc/yum.repos.d/*.repo /home/stack/DIB', user='stack')
        # NOTE(Gonéri): Hack to be sure DIB won't complain because of missing gpg files
#        self.run('sed -i "s,gpgcheck=1,gpgcheck=0," /home/stack/DIB/*.repo', user='stack')
        dib_yum_repo_conf = self.run('find /home/stack/DIB -type f', user='stack')[0].split()
        virt_setup_env = template.render(
            {
                'dib_yum_repo_conf': dib_yum_repo_conf,
                'node': {
                    'count': 2,
                    'mem': 6144,
                    'cpu': 2
                },
                'undercloud_node_mem': 8192,
                'guest_image_name': '/home/stack/guest_image.qcow2',
                'rhsm': {
                    'user': rhsm_login,
                    'password': rhsm_password
                }})
        self.create_file('virt-setup-env', virt_setup_env, user='stack')
        self.run('virsh destroy instack', ignore_error=True)
        self.run('virsh undefine instack --remove-all-storage', ignore_error=True)
        self.run('source virt-setup-env; instack-virt-setup', user='stack')
        undercloud_ip = self.run(
            '/sbin/ip n | grep $(tripleo get-vm-mac instack) | awk \'{print $1;}\'',
            user='stack')[0]
        assert undercloud_ip, 'undercloud should have an IP'
        undercloud = Undercloud(hostname=undercloud_ip,
                                via_ip=self.hostname,
                                user='root',
                                key_filename=self._key_filename)
        return undercloud
