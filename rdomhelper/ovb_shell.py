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

import click
import json
import yaml

import logging
import sys


from rdomhelper import logger
from rdomhelper import ovb_bmc
from rdomhelper import ovb_undercloud
import rdomhelper.provisioners.openstack.provisioner as os_provisioner
from rdomhelper.provisioners.openstack import utils as os_utils

import neutronclient.common.exceptions
import neutronclient.v2_0.client

LOG = logging.getLogger('__chainsaw__')


def deploy_bm(nova_api, neutron, provisioner, instance_name, image_name, ip, flavor='m1.small'):
    body_value = {
        "port": {
            "admin_state_up": True,
            "name": instance_name + '_provision',
            "network_id": os_utils.get_network_id(nova_api, 'provision_bob'),
            'fixed_ips': [{'ip_address': ip}],
            'extra_dhcp_opts': [
                {'opt_name': 'bootfile-name',
                 'opt_value': 'http://192.0.2.240:8088/boot.ipxe',
                 'ip_version': '4'},
                {'opt_name': 'tftp-server',
                 'opt_value': '192.0.2.240',
                 'ip_version': '4'},
                {'opt_name': 'server-ip-address',
                 'opt_value': '192.0.2.240',
                 'ip_version': '4'}]}}
    response = neutron.create_port(body=body_value)
    provision_port_id = response['port']['id']
    mac_address = response['port']['mac_address']

    image_id_to_boot_from = os_utils.get_image_id(nova_api, image_name)
    flavor_id = os_utils.get_flavor_id(nova_api, flavor)
    # TODO(Gonéri): We don't need keypair for the BM nodes
    keypair_id = os_utils.get_keypair_id(nova_api, provisioner['keypair'])
    # Ensure with get DHCP lease on the provision network first
    nics = [{'port-id': provision_port_id}]

    os_instance = os_provisioner.build_openstack_instance(
        nova_api,
        instance_name,
        image_id_to_boot_from,
        flavor_id,
        keypair_id,
        nics)

    if not os_instance:
        LOG.error("deployment has failed")
        sys.exit(1)

    os_utils.add_security_groups(os_instance,
                                 provisioner['security-groups'])
    os_provisioner.add_provision_security_group(nova_api)
    os_utils.add_security_groups(os_instance, ['provision'])
    LOG.info("add security groups '%s'" %
             provisioner['security-groups'])
    LOG.info("instance '%s' ready to use" % instance_name)

    # the instance should be off for Ironic
    os_instance.stop()

    return mac_address


def set_dhcp_parameter(neutron, filename):
    new_port = {
        'extra_dhcp_opts': [
            {'opt_name': 'bootfile-name', 'opt_value': 'http://192.0.2.240:8088/' + filename, 'ip_version': 4, },
            {'opt_name': 'tftp-server', 'opt_value': '192.0.2.240', 'ip_version': '4'},
            {'opt_name': 'server-ip-address', 'opt_value': '192.0.2.240', 'ip_version': '4'}
        ]
    }

    for port in neutron.list_ports()['ports']:
        if port['name'].startswith('baremetal') and port['name'].endswith('_provision'):
            neutron.update_port(port['id'], {'port': new_port})


def purge_existing_ovb(nova_api, neutron):
    """Purge any trace of an existing OVB deployment.
    """
    for server in nova_api.servers.list():
        if server.name in ('bmc', 'undercloud'):
            server.delete()
        if server.name.startswith('baremetal_'):
            server.delete()
    for router in neutron.list_routers(name='bmc_router').get('routers'):
        for port in neutron.list_ports(device_id=router['id'])['ports']:
            if port.get('device_owner') == 'network:router_gateway':
                continue
            info = {'id': router['id'],
                    'port_id': port['id'],
                    'tenant_id': router.get('tenant_id'),
                    }
            neutron.remove_interface_router(router['id'], info)
        for subnet in neutron.list_subnets().get('subnets'):
            if not (subnet['name'].startswith('bmc_eth') or subnet['name'] == 'rdo-m-subnet'):
                continue
            try:
                neutron.remove_interface_router(router['id'], {'subnet_id': subnet['id']})
            except neutronclient.common.exceptions.NotFound:
                pass
        neutron.delete_router(router['id'])
        for port in neutron.list_ports()['ports']:
            if port['name'].endswith('_provision'):
                neutron.delete_port(port['id'])
    for net in neutron.list_networks().get('networks'):
        if not net['name'].startswith('provision_'):
            continue
        for port in neutron.list_ports(network_id=net['id'])['ports']:
            if port.get('device_owner') == 'network:router_interface':
                continue
            try:
                neutron.delete_port(port['id'])
            except neutronclient.common.exceptions.PortNotFoundClient:
                pass
        for subnet in neutron.list_subnets(network_id=net['id'])['subnets']:
            neutron.delete_subnet(subnet['id'])
        neutron.delete_network(net['id'])


def initialize_network(neutron):
    """Initialize an OVB network called provision_bob.
    """
    body_sample = {
        "network": {
            "name": 'provision_bob',
            "admin_state_up": True,
        }
    }
    netw = neutron.create_network(body=body_sample)['network']
    body_create_subnet = {
        'subnets': [{
            'name': 'rdo-m-subnet',
            'cidr': '192.0.2.0/24',
            'ip_version': 4,
            'network_id': netw['id'],
            'host_routes': [{
                'destination': '169.254.169.254/32',
                'nexthop': '192.0.2.240'
            }],
            'allocation_pools': [{'start': '192.0.2.30', 'end': '192.0.2.199'}]}]}
    response = neutron.create_subnet(body=body_create_subnet)
    return response['subnets'][0]['id']


@click.command()
@click.option('--os-auth-url', envvar='OS_AUTH_URL', required=True,
              help="Keystone auth url.")
@click.option('--os-username', envvar='OS_USERNAME', required=True,
              help="Openstack username account.")
@click.option('--os-password', envvar='OS_PASSWORD', required=True,
              help="Openstack password account.")
@click.option('--os-tenant-name', envvar='OS_TENANT_NAME', required=True,
              help="Openstack tenant name.")
@click.option('--config-file', required=True, type=click.File('rb'),
              help="Chainsaw path configuration file.")
def cli(os_auth_url, os_username, os_password, os_tenant_name, config_file):
    config = yaml.load(config_file)
    logger.setup_logging(config_file='/tmp/ovb.log')

    neutron = neutronclient.v2_0.client.Client(username=os_username,
                                               password=os_password,
                                               tenant_name=os_tenant_name,
                                               auth_url=os_auth_url)
    nova_api = os_utils.build_nova_api(os_auth_url, os_username,
                                       os_password, os_tenant_name)

    purge_existing_ovb(nova_api, neutron)
    rdo_m_subnet_id = initialize_network(neutron)
    bmc = ovb_bmc.OvbBmc(
        nova_api=nova_api,
        neutron=neutron,
        provisioner=config['provisioner'],
        key_filename=config['ssh']['private_key'],
        image_name='Fedora 23 x86_64',
        ip='192.0.2.254',
        os_username=os_username,
        os_password=os_password,
        os_tenant_name=os_tenant_name,
        os_auth_url=os_auth_url)
    bmc.attach_subnet_to_router(rdo_m_subnet_id)

    instackenv = []
    idx = 100
    # The IP should be in this range, this is the default DHCP range used by the introspection.
    # inspection_iprange = 192.0.2.100,192.0.2.120
    bm_nodes = [{'name': 'baremetal_%d' % i, 'mac': None} for i in range(0, 7)]
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for bm_node in bm_nodes:
            future = executor.submit(
                deploy_bm,
                nova_api,
                neutron,
                config['provisioner'],
                bm_node['name'],
                'ipxe.iso',
                '192.0.2.%d' % idx,
                flavor='m1.large')
            idx += 1
            bm_node['mac'] = future

        for bm_node in bm_nodes:
            pm_addr = bmc.register_host(bm_node['name'])
            instackenv.append({
                "pm_type": "pxe_ipmitool",
                "mac": [bm_node['mac'].result()],
                # TODO(Gonéri): We should get these informations from the baremetal node's flavor
                "cpu": "4",
                "memory": "8196",
                "disk": "80",
                "arch": "x86_64",
                "pm_user": "admin",
                "pm_password": "password",
                "pm_addr": pm_addr
            })
    undercloud = ovb_undercloud.OVBUndercloud(
        nova_api=nova_api,
        neutron=neutron,
        provisioner=config['provisioner'],
        key_filename=config['ssh']['private_key'],
        ip='192.0.2.240',
        flavor='m1.large')

    undercloud.rhsm_register({
        'login': config['rhsm']['login'],
        'password': config['rhsm'].get('password'),
        'pool_id': config['rhsm'].get('pool_id')})

    undercloud.create_stack_user()
    undercloud.create_file('instackenv.json', json.dumps(instackenv), user='stack')
    undercloud_conf = """
[DEFAULT]
local_ip = 192.0.2.240/24
local_interface = eth1
dhcp_start = 192.0.2.50
dhcp_end = 192.0.2.70
undercloud_public_vip = 192.0.2.200
undercloud_admin_vip = 192.0.2.201
[auth]
"""
    undercloud.create_file(
        'undercloud.conf',
        undercloud_conf.format(
            undercloud_ip=undercloud.hostname), user='stack')
    undercloud.configure(config['undercloud']['repositories'])
    undercloud.set_ctlplane_mtu(1400)
    undercloud.install(
        config['undercloud']['image_path'],
        config['undercloud']['image_checksum'])

    # HACK to route the bmc traffic, we should write the configuration
    undercloud.run('ip route add 10.130.0.0/16 via 192.0.2.1')

    undercloud.enable_neutron_hack(os_username, os_password, os_tenant_name, os_auth_url)
    undercloud.overcloud_image_upload(config['overcloud'])
    undercloud.load_instackenv()
    set_dhcp_parameter(neutron, filename='inspector.ipxe')
    undercloud.start_overcloud_inspector()
    set_dhcp_parameter(neutron, filename='boot.ipxe')
    undercloud.start_overcloud_deploy()

# This is for setuptools entry point.
main = cli
