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

from tripleowrapper.server import Server


class Undercloud(Server):
    def __init__(self, undercloud_ip, user, via_ip=None, key_filename=None):
        Server.__init__(self,
                        hostname=undercloud_ip,
                        user=user,
                        via_ip=via_ip,
                        key_filename=key_filename)

    def deploy(self, guest_image_path, guest_image_checksum, files):
        for name, file in files.items():
            self.fetch_image(
                path=file['path'],
                checksum=file['checksum'],
                dest='/home/stack/%s.tar' % name,
                user='stack')
            self.run('tar xf /home/stack/%s.tar' % name,
                     user='stack')
        self.fetch_image(
            path=guest_image_path,
            checksum=guest_image_checksum,
            dest='/home/stack/guest_image.qcow2',
            user='stack')
        hostname_s = self.run('hostname -s')[0].rstrip('\n')
        hostname_f = self.run('cat /etc/hostname')[0].rstrip('\n')
        self.run("sed 's,127.0.0.1,127.0.0.1 %s %s,' /etc/hosts" % (hostname_s, hostname_f))
        self.set_selinux('permissive')
        self.run('openstack undercloud install', user='stack')
        self.add_environment_file(user='stack', filename='stackrc')
        self.run('heat stack-list', user='stack')
        self.run('openstack overcloud image upload', user='stack')
        self.run('openstack baremetal import --json instackenv.json', user='stack')
        self.run('openstack baremetal configure boot', user='stack')
        self.run('openstack flavor create --id auto --ram 4096 --disk 40 --vcpus 1 baremetal', user='stack')

    def start_overcloud(self):
        self.run('openstack flavor set --property "cpu_arch"="x86_64" --property "capabilities:boot_option"="local" baremetal', user='stack')
        self.run('openstack overcloud deploy --templates -e /usr/share/openstack-tripleo-heat-templates/overcloud-resource-registry-puppet.yaml', user='stack')
