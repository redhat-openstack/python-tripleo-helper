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

import logging

from rdomhelper.server import Server

LOG = logging.getLogger('__chainsaw__')


class Undercloud(Server):
    def __init__(self, **kwargs):
        Server.__init__(self, **kwargs)

    def _retrieve_prebuilt_files(self, files):
        for name in sorted(files):
            self.fetch_image(
                path=files[name]['path'],
                checksum=files[name]['checksum'],
                dest='/home/stack/%s.tar' % name,
                user='stack')
            self.run('tar xf /home/stack/%s.tar' % name,
                     user='stack')

    def configure(self, repositories):
        self.enable_repositories(repositories)
        self.install_nosync()
        self.create_stack_user()
        self.install_base_packages()
        self.clean_system()
        self.yum_update()
        self.install_osp()

    def install(self, guest_image_path, guest_image_checksum):
        self.fetch_image(
            path=guest_image_path,
            checksum=guest_image_checksum,
            dest='/home/stack/guest_image.qcow2',
            user='stack')
        hostname_s = self.run('hostname -s')[0].rstrip('\n')
        hostname_f = self.run('cat /etc/hostname')[0].rstrip('\n')
        self.run("sed 's,127.0.0.1,127.0.0.1 %s %s,' /etc/hosts" % (hostname_s, hostname_f))
        self.set_selinux('permissive')

        instack_undercloud_ver, _ = self.run('repoquery --whatprovides /usr/share/instack-undercloud/puppet-stack-config/puppet-stack-config.pp')
        if instack_undercloud_ver.rstrip('\n') == 'instack-undercloud-0:2.2.0-1.el7ost.noarch':
            LOG.warn('Workaround for BZ1298189')
            self.run("sed -i \"s/.*Keystone_domain\['heat_domain'\].*/Service\['keystone'\] -> Class\['::keystone::roles::admin'\] -> Class\['::heat::keystone::domain'\]/\" /usr/share/instack-undercloud/puppet-stack-config/puppet-stack-config.pp")
        if self.run('rpm -qa openstack-ironic-api')[0].rstrip('\n') == 'openstack-ironic-api-4.2.2-3.el7ost.noarch':
            LOG.warn('Workaround for BZ1297796')
            self.run('systemctl start openstack-ironic-api.service')
        self.run('openstack undercloud install', user='stack')
        self.add_environment_file(user='stack', filename='stackrc')
        self.run('heat stack-list', user='stack')

    def deploy_overcloud(self, files):
        self.add_environment_file(user='stack', filename='stackrc')
        self._retrieve_prebuilt_files(files)
        self.run('openstack overcloud image upload', user='stack')
        self.run('openstack baremetal import --json instackenv.json', user='stack')
        self.run('openstack baremetal configure boot', user='stack')
        self.run('openstack flavor create --id auto --ram 4096 --disk 40 --vcpus 1 baremetal', user='stack', success_status=(0, 1))
        self.run('openstack flavor set --property "cpu_arch"="x86_64" --property "capabilities:boot_option"="local" baremetal', user='stack')
        self.run('for uuid in $(ironic node-list|awk \'/available/ {print $2}\'); do ironic node-update $uuid add properties/capabilities=profile:baremetal,boot_option:local; done', user='stack')
        self.run('openstack overcloud deploy --debug ' +
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
                 '--swift-storage-flavor baremetal', user='stack')
        self.run('test -f overcloudrc', user='stack')

    def run_tempest(self):
        self.add_environment_file(user='stack', filename='overcloudrc')
        self.run('test -d tempest || mkdir tempest', user='stack')
        self.yum_install(['openstack-tempest-liberty'])
        self.run('cd tempest && /usr/share/openstack-tempest-liberty/tools/configure-tempest-directory', user='stack')
        self.run('neutron net-show ext-net || neutron net-create ext-net', user='stack')
        self.run('neutron subnet-show ext-subnet || neutron subnet-create ext-net --name ext-subnet   --allocation-pool start=172.16.23.40,end=172.16.23.50   --disable-dhcp --gateway 172.16.23.1 172.16.23.0/24', user='stack')
        network_id = self.run('neutron net-show ext-net -F id -f value', user='stack')[0].rstrip('\n')
        self.run('cd tempest && tools/config_tempest.py --out etc/tempest.conf --network-id {network_id} --deployer-input ~/tempest-deployer-input.conf --debug --create --image /home/stack/guest_image.qcow2 identity.uri $OS_AUTH_URL identity.admin_password $OS_PASSWORD network.tenant_network_cidr 192.168.0.0/24 object-storage.operator_role swiftoperator compute.image_ssh_user cloud-user compute.ssh_user cloud-user scenario.ssh_user cloud-user compute.flavor_ref 2 compute.flavor_ref_alt 2'.format(network_id=network_id), user='stack')
        self.run('cd tempest && tools/run-tests.sh tempest', user='stack')
