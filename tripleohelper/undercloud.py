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
import yaml

from tripleohelper.server import Server

LOG = logging.getLogger('tripleohelper')


class Undercloud(Server):
    def __init__(self, **kwargs):
        self.baremetal_factory = None
        Server.__init__(self, **kwargs)
        self._nova_version = None

    def configure(self, repositories):
        """Prepare the system to be ready for an undercloud installation.
        """
        self.enable_repositories(repositories)
        self.create_stack_user()
        self.install_base_packages()
        self.clean_system()
        self.yum_update(allow_reboot=True)
        self.install_osp()
        self.set_selinux('permissive')
        self.fix_hostname()

    def set_ctlplane_mtu(self, mtu=1400):
        self.run((
            'find /etc/sysconfig/network-scripts '
            '-name "ifcfg-eth?" -exec sed -i \'$ iMTU="%d"\' {} \;') % mtu)
        self.run('systemctl restart network')

    def fix_hostname(self):
        hostname = self.run('hostname')[0].rstrip('\n')
        hostname_s = self.run('hostname -s')[0].rstrip('\n')
        hostname_f = self.run('cat /etc/hostname')[0].rstrip('\n')
        self.run("sed -i 's,127.0.0.1,127.0.0.1 %s %s %s undercloud.openstacklocal,' /etc/hosts" % (hostname_s, hostname_f, hostname))

    def openstack_undercloud_install(self):
        """Deploy an undercloud on the host.
        """
        instack_undercloud_ver, _ = self.run('repoquery --whatprovides /usr/share/instack-undercloud/puppet-stack-config/puppet-stack-config.pp')
        if instack_undercloud_ver.rstrip('\n') == 'instack-undercloud-0:2.2.0-1.el7ost.noarch':
            LOG.warn('Workaround for BZ1298189')
            self.run("sed -i \"s/.*Keystone_domain\['heat_domain'\].*/Service\['keystone'\] -> Class\['::keystone::roles::admin'\] -> Class\['::heat::keystone::domain'\]/\" /usr/share/instack-undercloud/puppet-stack-config/puppet-stack-config.pp")

        self.run('OS_PASSWORD=bob openstack undercloud install', user='stack')
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

    def write_instackenv(self, baremetal_factory):
        self.create_file(
            'instackenv.json',
            baremetal_factory.get_instackenv_json(), user='stack')

    def load_instackenv(self):
        """Load the instackenv.json file and wait till the ironic nodes are ready.
        TODO(Gonéri): should be splitted, write_instackenv() to generate the
        instackenv.json and instackenv_import() for the rest.
        """
        self.add_environment_file(user='stack', filename='stackrc')
        self.run('openstack baremetal import --json instackenv.json', user='stack')
        ironic_node_nbr = 0
        count_cmd = 'jq -M "{filter}|length" /home/stack/instackenv.json'
        # Nodes are either in the .nodes list or at the root of the document
        for f in ['.nodes', '.']:
            try:
                ironic_node_nbr = int(
                    self.run(count_cmd.format(filter=f), user='stack')[0])
            except ValueError:
                pass
            if ironic_node_nbr > 0:
                break
        self._wait_for_ironic_nodes(ironic_node_nbr)
        # register association with the newly created ironic nodes and the
        # existing barematal nodes in the factory
        self.baremetal_factory.set_ironic_uuid(self.list_nodes())
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

    def manage_overcloud_templates(self, templates):
        if templates:
            self.send_dir(templates, "/home/stack", user='stack')
        else:
            self.create_file(
                '/home/stack/network-environment.yaml',
                yaml.dump({'parameter_defaults': {'DnsServers': ['8.8.8.8', '8.8.4.4']}}),
                user='stack')

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

    def start_overcloud_deploy(self, deploy_command=None, **kwargs):
        # if ipxe is frozen, the VM will stay running.
        # https://bugzilla.redhat.com/show_bug.cgi?id=1310778
        self.baremetal_factory.shutdown_nodes(self)

        self.add_environment_file(user='stack', filename='stackrc')
        if not deploy_command:
            deploy_command = self._prepare_o_o_deploy_command(**kwargs)
        self.run(deploy_command, user='stack')
        self.run('test -f overcloudrc', user='stack')

    def nova_version(self):
        if self._nova_version:
            return self._nova_version
        nova_version = self.run('nova-manage --version')[0].split(".")[0]
        # NOTE: before liberty, versions were year-release-version
        # since liberty there is a major 2 digit version for each release
        return 11 if len(str(nova_version)) == 4 else nova_version
