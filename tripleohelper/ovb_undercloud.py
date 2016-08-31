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
from tripleohelper.undercloud import Undercloud
from tripleohelper.utils import pkg_data_filename

LOG = logging.getLogger('tripleohelper')


class OVBUndercloud(Undercloud):
    """An undercloud for OVB.

    This host is an undercloud deployed on a nova VM. The second NIC (eth1) will be included
    in to the br-ctlplane.
    """
    def __init__(self, **kwargs):
        if 'hostname' not in kwargs:
            kwargs['hostname'] = None
        Undercloud.__init__(self, **kwargs)

    def start(self, nova_api=None, neutron=None, provisioner=None, ip=None,
              flavor='m1.small', floating_ip=None, **kwargs):
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

        self.hostname = os_utils.add_a_floating_ip(nova_api, os_instance, floating_ip)
        os_utils.add_security_groups(os_instance,
                                     provisioner['security-groups'])
        os_provisioner.add_provision_security_group(nova_api)
        os_utils.add_security_groups(os_instance, ['provision'])
        LOG.info("add security groups '%s'" %
                 provisioner['security-groups'])

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

    def enable_neutron_hack(self, os_username, os_password, os_project_id, os_auth_url):
        """Enable the neutron hack on the undercloud.

        This script will watch the undercloud and copy any relevant network
        configuration in the host OpenStack. This is required to avoid the
        firewall limitations (no-spoofing and DHCP restriction).
        """
        self.yum_install(['python-neutronclient'])
        self.send_file(pkg_data_filename('static', 'ovb_fix_neutron_addr'), '/usr/local/bin/ovb_fix_neutron_addr', unix_mode=0o755)
        content = """
[Unit]
Description=OVB neutron hack Service
[Service]
ExecStart=/usr/local/bin/ovb_fix_neutron_addr  --os-user {os_username} --os-password {os_password} --os-project-id {os_project_id} --os-auth-url {os_auth_url}
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
                os_project_id=os_project_id,
                os_auth_url=os_auth_url))
        self.run('systemctl enable %s' % unit)
        self.run('systemctl start %s' % unit)

    def patch_ironic_ramdisk(self):
        """Clean the disk before flushing the new image.

        See: https://bugs.launchpad.net/ironic-lib/+bug/1550604
        """
        tmpdir = self.run('mktemp -d')[0].rstrip('\n')
        self.run('cd {tmpdir}; zcat /home/stack/ironic-python-agent.initramfs| cpio -id'.format(tmpdir=tmpdir))
        self.send_file(pkg_data_filename('static', 'ironic-wipefs.patch'), '/tmp/ironic-wipefs.patch')
        self.run('cd {tmpdir}; patch -p0 < /tmp/ironic-wipefs.patch'.format(tmpdir=tmpdir))
        self.run('cd {tmpdir}; find . | cpio --create --format=newc > /home/stack/ironic-python-agent.initramfs'.format(tmpdir=tmpdir))

    def start_overcloud_inspector(self):
        # ensure the overlying Neutron will request the nodes to boot
        # on the inspector.ipxe file
        self.baremetal_factory.pxe_netboot('inspector.ipxe')
        Undercloud.start_overcloud_inspector(self)

    def start_overcloud_deploy(self, **kargs):
        # ensure the overlying Neutron will request the nodes to boot
        # on the boot.ipxe file
        self.baremetal_factory.pxe_netboot('boot.ipxe')
        Undercloud.start_overcloud_deploy(self, **kargs)

    def load_instackenv(self):
        super(OVBUndercloud, self).load_instackenv()
        # register association with the newly created ironic nodes and the
        # existing barematal nodes in the factory
        self.baremetal_factory.set_ironic_uuid(self.list_nodes())
