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
import sys

import tripleohelper.provisioners.openstack.provisioner as os_provisioner
from tripleohelper.provisioners.openstack import utils as os_utils
from tripleohelper.server import Server
from tripleohelper.utils import pkg_data_filename
from tripleohelper.utils import protect_password

LOG = logging.getLogger('tripleohelper')


class OvbBmc(Server):
    """A virtual BMC for OVB.

    This host is a nova virtual machine that will host IPMI services. Ironic will
    use these services to manage the virtual-baremetal nodes.

    For each baremetal node, the BMC has:

    - an NIC (ethX) with a specific IP address
    - an openstackbmc instance (IPMI server) associated to the nova host
    """
    def __init__(
            self,
            nova_api=None, neutron=None, keypair=None,
            key_filename=None, security_groups=[], image_name=None, ip=None,
            flavor='m1.small', os_username=None,
            os_password=None, os_project_id=None, os_auth_url=None, **kwargs):

        assert key_filename
        self.nova_api = nova_api
        self.neutron = neutron
        self._keypair = keypair
        self.os_username = os_username
        self.os_password = os_password
        self.os_project_id = os_project_id
        self.os_auth_url = os_auth_url
        self._nic_cpt = 0
        self._bmc_range_start = 100

        body_value = {
            "port": {
                "admin_state_up": True,
                "name": 'bmc_provision',
                "network_id": os_utils.get_network_id(nova_api, 'provision_bob'),
                'fixed_ips': [{'ip_address': ip}]
            }
        }
        response = neutron.create_port(body=body_value)
        provision_port_id = response['port']['id']

        image_id_to_boot_from = os_utils.get_image_id(nova_api, image_name)
        flavor_id = os_utils.get_flavor_id(nova_api, flavor)
        keypair_id = os_utils.get_keypair_id(nova_api, self._keypair)
        # TODO(Gonéri): this enforce the use of a private network called 'private'
        network_id = os_utils.get_network_id(nova_api, 'private')
        nics = [{'net-id': network_id}, {'port-id': provision_port_id}]

        self.os_instance = os_provisioner.build_openstack_instance(
            nova_api,
            'bmc',
            image_id_to_boot_from,
            flavor_id,
            keypair_id,
            nics)

        if not self.os_instance:
            LOG.error("deployment has failed")
            sys.exit(1)

        bmc_ip = os_utils.add_a_floating_ip(nova_api, self.os_instance)
        os_utils.add_security_groups(self.os_instance,
                                     security_groups)
        os_provisioner.add_provision_security_group(nova_api)
        os_utils.add_security_groups(self.os_instance, ['provision'])
        LOG.info("add security groups '%s'" % security_groups)

        Server.__init__(self, hostname=bmc_ip, key_filename=key_filename, **kwargs)

        self.router_id = self.neutron.list_routers(name='router').get('routers')[0]['id']
        body_sample = {
            "network": {
                "name": 'provision_bmc',
                "admin_state_up": True,
            }
        }
        self._bmc_net = self.neutron.create_network(body=body_sample)['network']
        os_utils.get_network_id(self.nova_api, 'provision_bob')

        self.send_file(pkg_data_filename('static', 'openstackbmc'), '/usr/local/bin/openstackbmc', unix_mode=0o755)
        self.yum_install(['https://www.rdoproject.org/repos/rdo-release.rpm'])
        self.yum_install(['python-novaclient', 'python-neutronclient', 'python-keystoneclient', 'python-pip', 'python2-oslo-utils', 'python-crypto'])
        self.run('pip install pyghmi')

    def attach_subnet_to_router(self, subnet_id):
        form_data = {'subnet_id': subnet_id}
        self.neutron.add_interface_router(self.router_id, form_data)

    def register_host(self, bm_instance):
        """Register an existing nova VM.

        A new interface will be attached to the BMC host with a new IP. An openstackbmc
        service will be binded to this IP.

        Once the VM has been registered, it is possible to use IPMI on this IP
        to start or stop the virtual machine.
        """
        bmc_ip = '10.130.%d.100' % (self._bmc_range_start + self._nic_cpt)
        bmc_net = '10.130.%d.0' % (self._bmc_range_start + self._nic_cpt)
        bmc_gw = '10.130.%d.1' % (self._bmc_range_start + self._nic_cpt)
        device = 'eth%d' % (2 + self._nic_cpt)
        body_create_subnet = {
            'subnets': [{
                'name': 'bmc_' + device,
                'cidr': bmc_net + '/24',
                'ip_version': 4,
                'network_id': self._bmc_net['id']}]}
        subnet_id = self.neutron.create_subnet(body=body_create_subnet)['subnets'][0]['id']
        self.attach_subnet_to_router(subnet_id)
        self.os_instance.interface_attach(None, self._bmc_net['id'], bmc_ip)
        content = """
DEVICE="{device}"
BOOTPROTO=static
IPADDR={bmc_ip}
NETMASK=255.255.255.0
ONBOOT=yes
"""
        self.create_file(
            '/etc/sysconfig/network-scripts/ifcfg-%s' % device,
            content=content.format(device=device, bmc_ip=bmc_ip, bmc_gw=bmc_gw))

        content = """
192.0.2.0/24 via {bmc_gw}
"""
        self.create_file(
            '/etc/sysconfig/network-scripts/route-%s' % device,
            content=content.format(bmc_gw=bmc_gw))
        self.run('ifup %s' % device)

        # Ensure the outgoing traffic go through the correct NIC to avoid spoofing
        # protection
        # TODO(Gonéri): This should be persistant.
        self.run('ip rule add from %s table %d' % (bmc_ip, self._nic_cpt + 2))
        self.run('ip route add default via %s dev %s table %d' % (bmc_gw, device, self._nic_cpt + 2))

        content = """
[Unit]
Description=openstack-bmc {bm_instance} Service
[Service]
ExecStart=/usr/local/bin/openstackbmc  --os-user {os_username} --os-password {os_password} --os-project-id {os_project_id} --os-auth-url {os_auth_url} --instance {bm_instance} --address {bmc_ip}
User=root
StandardOutput=kmsg+console
StandardError=inherit
Restart=always
[Install]
WantedBy=multi-user.target
"""
        unit = 'openstack-bmc-%d.service' % self._nic_cpt
        self.create_file(
            '/usr/lib/systemd/system/%s' % unit,
            content.format(
                os_username=self.os_username,
                os_password=protect_password(self.os_password),
                os_project_id=self.os_project_id,
                os_auth_url=self.os_auth_url,
                bm_instance=bm_instance,
                bmc_ip=bmc_ip))
        self.run('systemctl enable %s' % unit)
        self.run('systemctl start %s' % unit)
        self._nic_cpt += 1

        return bmc_ip
