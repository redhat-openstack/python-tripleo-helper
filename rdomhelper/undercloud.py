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
import time

from rdomhelper.server import Server

LOG = logging.getLogger('__chainsaw__')


class Undercloud(Server):
    def __init__(self, **kwargs):
        Server.__init__(self, **kwargs)

    def configure(self, repositories):
        """Prepare the system to be ready for an undercloud installation.
        """
        self.enable_repositories(repositories)
        self.install_nosync()
        self.create_stack_user()
        self.install_base_packages()
        self.clean_system()
        self.yum_update()
        self.install_osp()
        self.set_selinux('permissive')
        self.fix_hostname()

    def set_ctlplane_mtu(self, mtu=1400):
        # TODO(Gonéri): Ensure we will get a MTU 1400 on the br-ctlplane for OVB or libvirt
        # https://review.openstack.org/#/c/288041
        self.yum_install(['instack-undercloud'])
        # Ensure the os-net-config configuration has not been generated yet.
        self.run('test ! -f /etc/os-net-config/config.json')
        self.run('sed -i \'s/"name": "br-ctlplane",/"name": "br-ctlplane",\\n      "mtu": %d,/\' /usr/share/instack-undercloud/undercloud-stack-config/config.json.template' % mtu)
        self.run('sed -i \'s/"primary": "true"/"primary": "true",\\n        "mtu": %d/\' /usr/share/instack-undercloud/undercloud-stack-config/config.json.template' % mtu)

    def fix_hostname(self):
        hostname = self.run('hostname')[0].rstrip('\n')
        hostname_s = self.run('hostname -s')[0].rstrip('\n')
        hostname_f = self.run('cat /etc/hostname')[0].rstrip('\n')
        self.run("sed -i 's,127.0.0.1,127.0.0.1 %s %s %s undercloud.openstacklocal,' /etc/hosts" % (hostname_s, hostname_f, hostname))

    def openstack_undercloud_install(self, guest_image_path, guest_image_checksum):
        """Deploy an undercloud on the host.
        """
        # TODO(Gonéri) this method should be splitted/simplified.
        self.fetch_image(
            path=guest_image_path,
            checksum=guest_image_checksum,
            dest='/home/stack/guest_image.qcow2',
            user='stack')

        instack_undercloud_ver, _ = self.run('repoquery --whatprovides /usr/share/instack-undercloud/puppet-stack-config/puppet-stack-config.pp')
        if instack_undercloud_ver.rstrip('\n') == 'instack-undercloud-0:2.2.0-1.el7ost.noarch':
            LOG.warn('Workaround for BZ1298189')
            self.run("sed -i \"s/.*Keystone_domain\['heat_domain'\].*/Service\['keystone'\] -> Class\['::keystone::roles::admin'\] -> Class\['::heat::keystone::domain'\]/\" /usr/share/instack-undercloud/puppet-stack-config/puppet-stack-config.pp")

        self.run('openstack undercloud install', user='stack')
        # NOTE(Gonéri): we also need this after the overcloud deployment
        if self.run('rpm -qa openstack-ironic-api')[0].rstrip('\n') == 'openstack-ironic-api-4.2.2-3.el7ost.noarch':
            LOG.warn('Workaround for BZ1297796')
            self.run('systemctl start openstack-ironic-api.service')
        self.add_environment_file(user='stack', filename='stackrc')
        self.run('heat stack-list', user='stack')

    def overcloud_image_upload(self, files):
        """Wrapper for: openstack overcloud image upload

        :param files: a list of files to retrieve first.
        """
        for name in sorted(files):
            self.fetch_image(
                path=files[name]['image_path'],
                checksum=files[name]['checksum'],
                dest='/home/stack/%s.tar' % name,
                user='stack')
            self.run('tar xf /home/stack/%s.tar' % name,
                     user='stack')
        self.run('openstack overcloud image upload', user='stack')

    def load_instackenv(self):
        """Load the instackenv.json file and wait till the ironic nodes are ready.
        """
        self.add_environment_file(user='stack', filename='stackrc')
        self.run('openstack baremetal import --json instackenv.json', user='stack')
        ironic_node_nbr = int(self.run('grep --count \'"cpu"\' instackenv.json', user='stack')[0])
        self._wait_for_ironic_nodes(ironic_node_nbr)
        self.run('openstack baremetal configure boot', user='stack')

    def _wait_for_ironic_nodes(self, expected_nbr):
        LOG.debug('Waiting for %s nodes to be properly registred.' % expected_nbr)
        for i in range(1, 18):
            current_nbr = int(self.run('ironic node-list|grep -c "power off"', user='stack')[0])
            LOG.debug('% 2d/% 2d' % (current_nbr, expected_nbr))
            if current_nbr >= expected_nbr:
                LOG.debug('%s ironic nodes are now available.' % current_nbr)
                break
            time.sleep(10)
        else:
            LOG.debug(
                'registration of %s nodes times out, succeed to register %s nodes' % (
                    expected_nbr, current_nbr))
            # TODO(Gonéri): need a better execpetion
            raise Exception()

    def start_overcloud_inspector(self):
        """Wrapper for: openstack baremetal introspection bulk start
        """
        self.add_environment_file(user='stack', filename='stackrc')
        self.run('openstack baremetal introspection bulk start', user='stack')

    def start_overcloud_deploy(self):
        self.add_environment_file(user='stack', filename='stackrc')
        self.run('openstack flavor create --id auto --ram 4096 --disk 40 --vcpus 1 baremetal', user='stack', success_status=(0, 1))
        self.run('openstack flavor set --property "cpu_arch"="x86_64" --property "capabilities:boot_option"="local" baremetal', user='stack')
        self.run('openstack flavor set --property "capabilities:profile"="baremetal" baremetal', user='stack')
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
        """Call tempest from this host.

        Launch tempest to validate the newly deployed OpenStack instance.
        """
        self.add_environment_file(user='stack', filename='overcloudrc')
        self.run('test -d tempest || mkdir tempest', user='stack')
        self.yum_install(['openstack-tempest-liberty'])
        self.run('cd tempest && /usr/share/openstack-tempest-liberty/tools/configure-tempest-directory', user='stack')
        self.run('neutron net-show ext-net || neutron net-create ext-net', user='stack')
        self.run('neutron subnet-show ext-subnet || neutron subnet-create ext-net --name ext-subnet   --allocation-pool start=172.16.23.40,end=172.16.23.50   --disable-dhcp --gateway 172.16.23.1 172.16.23.0/24', user='stack')
        network_id = self.run('neutron net-show ext-net -F id -f value', user='stack')[0].rstrip('\n')
        self.run('cd tempest && tools/config_tempest.py --out etc/tempest.conf --network-id {network_id} --deployer-input ~/tempest-deployer-input.conf --debug --create --image /home/stack/guest_image.qcow2 identity.uri $OS_AUTH_URL identity.admin_password $OS_PASSWORD network.tenant_network_cidr 192.168.0.0/24 object-storage.operator_role swiftoperator compute.image_ssh_user cloud-user compute.ssh_user cloud-user scenario.ssh_user cloud-user compute.flavor_ref 2 compute.flavor_ref_alt 2'.format(network_id=network_id), user='stack')
        self.run('cd tempest && tools/run-tests.sh tempest', user='stack')
