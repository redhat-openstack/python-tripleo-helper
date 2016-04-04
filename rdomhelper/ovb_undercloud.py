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

import rdomhelper.provisioners.openstack.provisioner as os_provisioner
from rdomhelper.provisioners.openstack import utils as os_utils
from rdomhelper.undercloud import Undercloud

LOG = logging.getLogger('__chainsaw__')


class OVBUndercloud(Undercloud):
    """An undercloud for OVB.

    This host is an undercloud deployed on a nova VM. The second NIC (eth1) will be included
    in to the br-ctlplane.
    """
    def __init__(self, nova_api=None, neutron=None, provisioner=None, ip=None, flavor='m1.small', **kwargs):
        body_value = {
            "port": {
                "admin_state_up": True,
                "name": 'undercloud_provision',
                "network_id": os_utils.get_network_id(nova_api, 'provision_bob'),
                'fixed_ips': [{'ip_address': ip}],
                'allowed_address_pairs': [{"ip_address": "169.254.169.254/32"}]
            }
        }

        response = neutron.create_port(body=body_value)
        provision_port_id = response['port']['id']
        image_id_to_boot_from = os_utils.get_image_id(nova_api, provisioner['image']['name'])
        flavor_id = os_utils.get_flavor_id(nova_api, flavor)
        keypair_id = os_utils.get_keypair_id(nova_api, provisioner['keypair'])
        network_id = os_utils.get_network_id(nova_api, provisioner['network'])
        nics = [{'net-id': network_id}, {'port-id': provision_port_id}]

        os_instance = os_provisioner.build_openstack_instance(
            nova_api,
            'undercloud',
            image_id_to_boot_from,
            flavor_id,
            keypair_id,
            nics)
        if not os_instance:
            LOG.error("deployment has failed")
            sys.exit(1)

        undercloud_ip = os_utils.add_a_floating_ip(nova_api, os_instance)
        os_utils.add_security_groups(os_instance,
                                     provisioner['security-groups'])
        os_provisioner.add_provision_security_group(nova_api)
        os_utils.add_security_groups(os_instance, ['provision'])
        LOG.info("add security groups '%s'" %
                 provisioner['security-groups'])

        Undercloud.__init__(self, hostname=undercloud_ip, **kwargs)

        content = """
DEVICE="eth1"
BOOTPROTO=static
IPADDR=192.0.2.240
NETMASK=255.255.255.0
ONBOOT=yes
MTU=1400
"""
        self.create_file(
            '/etc/sysconfig/network-scripts/ifcfg-eth1',
            content=content)
        self.run('ifup eth1')
        LOG.info("undercloud is ready")

    def enable_neutron_hack(self, os_username, os_password, os_tenant_name, os_auth_url):
        """Enable the neutron hack on the undercloud.

        This script will watch the undercloud and copy any relevant network
        configuration in the host OpenStack. This is required to avoid the
        firewall limitations (no-spoofing and DHCP restriction).
        """
        self.yum_install(['python-neutronclient'])
        self.send_file('static/ovb_fix_neutron_addr', '/usr/local/bin/ovb_fix_neutron_addr', unix_mode=0o755)
        content = """
[Unit]
Description=OVB neutron hack Service
[Service]
ExecStart=/usr/local/bin/ovb_fix_neutron_addr  --os-user {os_username} --os-password {os_password} --os-tenant {os_tenant_name} --os-auth-url {os_auth_url}
User=root
StandardOutput=kmsg+console
StandardError=inherit
Restart=always
[Install]
WantedBy=multi-user.target
"""
        unit = 'ovb_fix_neutron_addr.service'
        self.create_file(
            '/usr/lib/systemd/system/%s' % unit,
            content.format(
                os_username=os_username,
                os_password=os_password,
                os_tenant_name=os_tenant_name,
                os_auth_url=os_auth_url))
        self.run('systemctl enable %s' % unit)
        self.run('systemctl start %s' % unit)

    def patch_ironic_ramdisk(self):
        """Clean the disk before flushing the new image.

        See: https://bugs.launchpad.net/ironic-lib/+bug/1550604
        """
        tmpdir = self.run('mktemp -d')[0].rstrip('\n')
        self.run('cd {tmpdir}; zcat /home/stack/ironic-python-agent.initramfs| cpio -id'.format(tmpdir=tmpdir))
        self.send_file('static/ironic-wipefs.patch', '/tmp/ironic-wipefs.patch')
        self.run('cd {tmpdir}; patch -p0 < /tmp/ironic-wipefs.patch'.format(tmpdir=tmpdir))
        self.run('cd {tmpdir}; find . | cpio --create --format=newc > /home/stack/ironic-python-agent.initramfs'.format(tmpdir=tmpdir))
