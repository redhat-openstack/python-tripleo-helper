#!/usr/bin/env python
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

import concurrent.futures
import json
import logging

import rdomhelper.baremetal
from rdomhelper import ovb_bmc
import rdomhelper.provisioners.openstack.provisioner as os_provisioner
from rdomhelper.provisioners.openstack import utils as os_utils
import rdomhelper.server as server

LOG = logging.getLogger('__chainsaw__')


class Baremetal(server.Server):
    """A baremetal node."""
    def __init__(self, nova_api, neutron, keypair, key_filename, security_groups, name):
        server.Server.__init__(self, None, via_ip='192.0.2.240', key_filename=key_filename)
        self.nova_api = nova_api
        self.neutron = neutron
        self.mac = None
        self._os_instance = None
        self._provision_port_id = None
        self._keypair = keypair
        self._key_filename = key_filename
        self._security_groups = security_groups
        self.name = name
        self.uuid = None
        self.flavor = None
        self.status = None

    def deploy(self, image_name, ip, flavor='m1.small'):
        """Create the node.

        This method should only be called by the BaremetalFactory.
        """
        body_value = {
            "port": {
                "admin_state_up": True,
                "name": self.name + '_provision',
                "network_id": os_utils.get_network_id(self.nova_api, 'provision_bob'),
                'fixed_ips': [{'ip_address': ip}]}}
        response = self.neutron.create_port(body=body_value)
        self._provision_port_id = response['port']['id']
        self.mac = response['port']['mac_address']

        image_id_to_boot_from = os_utils.get_image_id(self.nova_api, image_name)
        flavor_id = os_utils.get_flavor_id(self.nova_api, flavor)
        # TODO(Gonéri): We don't need keypair for the BM nodes
        keypair_id = os_utils.get_keypair_id(self.nova_api, self._keypair)
        # Ensure with get DHCP lease on the provision network first
        nics = [{'port-id': self._provision_port_id}]

        self._os_instance = os_provisioner.build_openstack_instance(
            self.nova_api,
            self.name,
            image_id_to_boot_from,
            flavor_id,
            keypair_id,
            nics)

        if not self._os_instance:
            LOG.error("deployment has failed")
            raise Exception()

        os_provisioner.add_provision_security_group(self.nova_api)
        os_utils.add_security_groups(self._os_instance, ['provision'])
        os_utils.add_security_groups(self._os_instance, self._security_groups)
        LOG.info("add security groups '%s'" % self._security_groups)
        LOG.info("instance '%s' ready to use" % self.name)

        # the instance should be off for Ironic
        self._os_instance.stop()

    def admin_state_up(self, state):
        """Turns up/down the network connection."""
        self.neutron.update_port(self._provision_port_id, {'port': {'admin_state_up': state}})

    def pxe_netboot(self, filename):
        """Specify which file ipxe should load during the netboot."""
        new_port = {
            'extra_dhcp_opts': [
                {'opt_name': 'bootfile-name', 'opt_value': 'http://192.0.2.240:8088/' + filename, 'ip_version': 4, },
                {'opt_name': 'tftp-server', 'opt_value': '192.0.2.240', 'ip_version': '4'},
                {'opt_name': 'server-ip-address', 'opt_value': '192.0.2.240', 'ip_version': '4'}
            ]
        }
        self.neutron.update_port(self._provision_port_id, {'port': new_port})

    def refresh_nova_instance(self):
        self._os_instance = self.nova_api.servers.get(self._os_instance.id)

    def shutdown(self):
        self.refresh_nova_instance()
        if self._os_instance.status == 'ACTIVE':
            self._os_instance.stop()

    def refresh_status(self, undercloud):
        self.refresh_nova_instance()
        ports = self.neutron.list_ports(name='%s_provision' % self.name)
        self.hostname = ports['ports'][0]['fixed_ips'][0]['ip_address']
        self.via_ip = undercloud.hostname
        self._provision_port_id = ports['ports'][0]['id']
        if self._os_instance.status == 'SHUTOFF':
            return
        command = """cat .ssh/authorized_keys | ssh -o UserKnownHostsFile=/dev/null -o PasswordAuthentication=no -o stricthostkeychecking=no heat-admin@{node_ip} 'sudo bash -c "cat >> ~root/.ssh/authorized_keys"'"""
        # The VM may be blocked because of ipxe
        undercloud.run(command.format(node_ip=self.hostname), user='stack', success_status=(0, 255,))


class BaremetalFactory(rdomhelper.baremetal.BaremetalFactory):
    def __init__(self, nova_api, neutron, keypair, key_filename, security_groups,
                 os_params={}):
        self.instackenv = []
        self.nova_api = nova_api
        self.neutron = neutron
        self._idx = 100
        self._keypair = keypair
        self._key_filename = key_filename
        self._security_groups = security_groups
        self.nodes = []

        if os_params:
            self.bmc = self.create_bmc(**os_params)

    def initialize(self, size=2):
        """Populate the node poll.

        :param size: the number of node to create.
        """
        # The IP should be in this range, this is the default DHCP range used by the introspection.
        # inspection_iprange = 192.0.2.100,192.0.2.120
        for i in range(0, size):
            self.nodes.append(
                Baremetal(
                    self.nova_api,
                    self.neutron,
                    self._keypair,
                    self._key_filename,
                    self._security_groups,
                    name='baremetal_%d' % i))
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for bm_node in self.nodes:
                future = executor.submit(
                    bm_node.deploy,
                    'ipxe.iso',
                    '192.0.2.%d' % self._idx,
                    flavor='m1.large')
                self._idx += 1
                bm_node._future = future
            for bm_node in self.nodes:
                bm_node._future.result()
                pm_addr = self.bmc.register_host(bm_node.name)
                self.instackenv.append({
                    "pm_type": "pxe_ipmitool",
                    "mac": [bm_node.mac],
                    # TODO(Gonéri): We should get these informations from the baremetal node's flavor
                    "cpu": "4",
                    "memory": "8196",
                    "disk": "80",
                    "arch": "x86_64",
                    "pm_user": "admin",
                    "pm_password": "password",
                    "pm_addr": pm_addr
                })

    def set_ironic_uuid(self, uuid_list):
        """Map a list of Ironic UUID to BM nodes.
        """
        # TODO(Gonéri): ensure we adjust the correct node
        i = iter(self.nodes)
        for uuid in uuid_list:
            node = next(i)
            node.uuid = uuid

    def reload_environment(self, undercloud):
        servers = {}
        for s in self.nova_api.servers.list():
            if s.name.startswith('baremetal_'):
                servers[s.name] = s
        for name, s in sorted(servers.items()):
            node = Baremetal(
                self.nova_api,
                self.neutron,
                keypair=self._keypair,
                key_filename=self._key_filename,
                security_groups=self._security_groups,
                name=s.name)
            node._os_instance = s
            self.nodes.append(node)
        instackenv = json.loads(undercloud.run('cat instackenv.json', user='stack')[0])
        i = iter(self.nodes)
        for instack_node in instackenv:
            node = next(i)
            node.mac = instack_node['mac'][0]
            node.refresh_status(undercloud)
        # restore the flavor
        undercloud.add_environment_file(user='stack', filename='stackrc')
        command = """ironic node-list --fields properties|sed -n 's/.*profile:\([-_a-z]*\),.*/\\1/p'"""
        flavor_list = undercloud.run(command, user='stack')[0].split()
        if flavor_list:
            i = iter(flavor_list)
            for node in self.nodes:
                node.flavor = next(i)

    def create_bmc(self, os_username, os_password, os_tenant_name, os_auth_url):
        """Deploy the BMC machine.

        This machine hosts the ipmi servers, each ipmi server is associated to a baremetal
        node and has its own IP.
        """
        bmc = ovb_bmc.OvbBmc(
            nova_api=self.nova_api,
            neutron=self.neutron,
            keypair=self._keypair,
            key_filename=self._key_filename,
            security_groups=self._security_groups,
            image_name='Fedora 23 x86_64',
            ip='192.0.2.254',
            os_username=os_username,
            os_password=os_password,
            os_tenant_name=os_tenant_name,
            os_auth_url=os_auth_url)
        return bmc
