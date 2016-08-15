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

from tripleohelper.server import Server

LOG = logging.getLogger('tripleohelper')


class Undercloud(Server):
    def __init__(self, **kwargs):
        self.baremetal_factory = None
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
        # TODO(Gonéri) we don't use this image
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

    def fetch_overcloud_images(self, files):
        if files:
            for name in sorted(files):
                self.fetch_image(
                    path=files[name]['image_path'],
                    dest='/home/stack/%s.tar' % name,
                    checksum=files[name].get('checksum'),
                    user='stack')
                self.run('tar xf /home/stack/%s.tar' % name,
                         user='stack')
        else:
            # OSP specific
            self.yum_install(['rhosp-director-images', 'rhosp-director-images-ipa'])
            self.run('find /usr/share/rhosp-director-images/ -type f -name "*.tar" -exec tar xf {} \;', user='stack')

    def overcloud_image_upload(self):
        """Wrapper for: openstack overcloud image upload

        :param files: a list of files to retrieve first.
        """
        self.add_environment_file(user='stack', filename='stackrc')
        self.run('openstack overcloud image upload', user='stack')

    def load_instackenv(self):
        """Load the instackenv.json file and wait till the ironic nodes are ready.
        TODO(Gonéri): should be splitted, write_instackenv() to generate the
        instackenv.json and instackenv_import() for the rest.
        """
        self.create_file(
            'instackenv.json',
            self.baremetal_factory.get_instackenv_json(), user='stack')
        self.add_environment_file(user='stack', filename='stackrc')
        self.run('openstack baremetal import --json instackenv.json', user='stack')
        ironic_node_nbr = int(self.run('cat /home/stack/instackenv.json |jq -M ".|length"', user='stack')[0])
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

    def _prepare_o_o_deploy_command(self, environments=[], **kwargs):
        args = {
            'control_scale': 0,
            'compute_scale': 0,
            'ceph_storage_scale': 0,
            'block_storage_scale': 0,
            'swift_storage_scale': 0,
            'control_flavor': 'baremetal',
            'compute_flavor': 'baremetal',
            'ceph_storage_flavor': 'baremetal',
            'block_storage_flavor': 'baremetal',
            'swift_storage_flavor': 'baremetal'}
        args.update(**kwargs)
        deploy_command = (
            'openstack overcloud deploy '
            '--templates '
            '--log-file overcloud_deployment.log '
            '--ntp-server north-america.pool.ntp.org '
            '--control-scale {control_scale} '
            '--compute-scale {compute_scale} '
            '--ceph-storage-scale {ceph_storage_scale} '
            '--block-storage-scale {block_storage_scale} '
            '--swift-storage-scale {swift_storage_scale} '
            '--control-flavor {control_flavor} '
            '--compute-flavor {compute_flavor} '
            '--ceph-storage-flavor {ceph_storage_flavor} '
            '--block-storage-flavor {block_storage_flavor} '
            '--swift-storage-flavor {swift_storage_flavor} ').format(**args)
        for e in environments:
            deploy_command += '-e '
            deploy_command += e
            deploy_command += ' '
        return deploy_command

    def create_flavor(self, name):
        """Create a new baremetal flavor.

        :param name: the name of the flavor
        """
        self.add_environment_file(user='stack', filename='stackrc')
        self.run('openstack flavor create --id auto --ram 4096 --disk 40 --vcpus 1 baremetal', user='stack', success_status=(0, 1))
        self.run('openstack flavor set --property "cpu_arch"="x86_64" --property "capabilities:boot_option"="local" baremetal', user='stack')
        self.run('openstack flavor set --property "capabilities:profile"="baremetal" baremetal', user='stack')

    def list_nodes(self):
        """List the Ironic nodes UUID."""
        self.add_environment_file(user='stack', filename='stackrc')
        ret, _ = self.run("ironic node-list --fields uuid|awk '/-.*-/ {print $2}'", user='stack')
        # NOTE(Gonéri): the good new is, the order of the nodes is preserved and follow the one from
        # the instackenv.json, BUT it may be interesting to add a check.
        return ret.split()

    def set_flavor(self, node, flavor):
        """Set a flavor to a given ironic node.

        :param uuid: the ironic node UUID
        :param flavor: the flavor name
        """
        command = (
            'ironic node-update {uuid} add '
            'properties/capabilities=profile:{flavor},boot_option:local').format(
                uuid=node.uuid, flavor=flavor)

        node.flavor = flavor
        self.add_environment_file(user='stack', filename='stackrc')
        self.run(command, user='stack')

    def start_overcloud_deploy(self, **kwargs):
        # if ipxe is frozen, the VM will stay running.
        # https://bugzilla.redhat.com/show_bug.cgi?id=1310778
        self.baremetal_factory.shutdown_nodes(self)

        self.add_environment_file(user='stack', filename='stackrc')
        o_o_deploy_command = self._prepare_o_o_deploy_command(**kwargs)
        self.run(o_o_deploy_command, user='stack')
        self.run('test -f overcloudrc', user='stack')
