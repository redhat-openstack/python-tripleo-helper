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
import time
import yaml

import logging

import tripleohelper.chaos_monkey
from tripleohelper import logger
from tripleohelper import ovb_baremetal
from tripleohelper import ovb_undercloud
from tripleohelper.provisioners.openstack import utils as os_utils
import tripleohelper.undercloud
import tripleohelper.watcher

import neutronclient.common.exceptions
import neutronclient.v2_0.client

LOG = logging.getLogger('tripleohelper')


def purge_existing_ovb(nova_api, neutron):
    """Purge any trace of an existing OVB deployment.
    """
    LOG.info('Cleaning up OVB environment from the tenant.')
    for server in nova_api.servers.list():
        if server.name in ('bmc', 'undercloud'):
            server.delete()
        if server.name.startswith('baremetal_'):
            server.delete()
    for router in neutron.list_routers().get('routers'):
        if router['name'] not in ('router', 'bmc_router'):
            continue
        for subnet in neutron.list_subnets().get('subnets'):
            if not (subnet['name'].startswith('bmc_eth') or subnet['name'] == 'rdo-m-subnet'):
                continue
            try:
                neutron.remove_interface_router(router['id'], {'subnet_id': subnet['id']})
            except neutronclient.common.exceptions.NotFound:
                pass
    try:
        bmc_router = neutron.list_routers(name='bmc_router').get('routers')[0]
        for port in neutron.list_ports(device_id=bmc_router['id'])['ports']:
            if port.get('device_owner') == 'network:router_gateway':
                continue
            info = {'id': router['id'],
                    'port_id': port['id'],
                    'tenant_id': bmc_router.get('tenant_id'),
                    }
            neutron.remove_interface_router(bmc_router['id'], info)
        neutron.delete_router(bmc_router['id'])
    except IndexError:  # already doesnt exist
        pass

    for _ in range(0, 5):
        try:
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
        except neutronclient.common.exceptions.Conflict:
            LOG.debug('waiting for all the ports to be freed...')
            time.sleep(5)
        else:
            return


def get_undercloud_ip(nova_api):
    i = nova_api.servers.list(search_opts={'name': 'undercloud'})
    try:
        return i[0].networks['private'][1]
    except IndexError:
        pass


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
            'gateway_ip': '192.0.2.1',
            'dns_nameservers': ['8.8.8.8', '8.8.4.4'],
            'allocation_pools': [{'start': '192.0.2.30', 'end': '192.0.2.199'}]}]}
    response = neutron.create_subnet(body=body_create_subnet)
    subnet_id = response['subnets'][0]['id']
    router = neutron.list_routers(name='router').get('routers')[0]
    response = neutron.add_interface_router(router['id'], {'subnet_id': subnet_id})


@click.command()
@click.option('--os-auth-url', envvar='OS_AUTH_URL', required=True,
              help="Keystone auth url.")
@click.option('--os-username', envvar='OS_USERNAME', required=True,
              help="Openstack username account.")
@click.option('--os-password', envvar='OS_PASSWORD', required=True,
              help="Openstack password account.")
@click.option('--os-project-id', envvar='OS_TENANT_ID', required=True,
              help="Openstack project ID.")
@click.option('--config-file', required=True, type=click.File('rb'),
              help="Chainsaw path configuration file.")
@click.argument('step', nargs=1, required=True,
                type=click.Choice(['provisioning', 'undercloud', 'overcloud']))
def cli(os_auth_url, os_username, os_password, os_project_id, config_file, step):
    config = yaml.load(config_file)
    logger.setup_logging(config_file='/tmp/ovb.log')
    undercloud = None
    baremetal_factory = None

    sess = os_utils.ks_session(os_auth_url, os_username, os_password, os_project_id)
    neutron = os_utils.build_neutron_client(sess)
    nova_api = os_utils.build_nova_api(sess)
    provisioner = config['provisioner']

    print('step: %s' % step)
    if step == 'provisioning':
        purge_existing_ovb(nova_api, neutron)
        initialize_network(neutron)
        undercloud = ovb_undercloud.OVBUndercloud(
            key_filename=config['ssh']['private_key']
        )
        undercloud.start(
            nova_api=nova_api,
            neutron=neutron,
            provisioner=config['provisioner'],
            ip='192.0.2.240',
            floating_ip=config['undercloud'].get('floating_ip'))

        undercloud.create_stack_user()

        baremetal_factory = ovb_baremetal.BaremetalFactory(
            nova_api,
            neutron,
            keypair=config['provisioner']['keypair'],
            key_filename=config['ssh']['private_key'],
            security_groups=config['provisioner']['security-groups'],
            os_params={'os_username': os_username,
                       'os_password': os_password,
                       'os_project_id': os_project_id,
                       'os_auth_url': os_auth_url})
        baremetal_factory.initialize(size=2)
        undercloud.write_instackenv(baremetal_factory)
        undercloud.ssh_pool.stop_all()
        print('done')
        exit(0)
    else:  # Restoring the environment
        undercloud_ip = get_undercloud_ip(nova_api)
        undercloud = tripleohelper.ovb_undercloud.OVBUndercloud(
            key_filename=config['ssh']['private_key'],
            hostname=undercloud_ip)
        baremetal_factory = ovb_baremetal.BaremetalFactory(
            nova_api,
            neutron,
            keypair=config['provisioner']['keypair'],
            key_filename=config['ssh']['private_key'],
            security_groups=config['provisioner']['security-groups'],
        )
        baremetal_factory.reload_environment(undercloud)
        undercloud.baremetal_factory = baremetal_factory

    if step == 'undercloud':
        undercloud.rhsm_register({
            'login': config['rhsm']['login'],
            'password': config['rhsm'].get('password'),
            'pool_id': config['rhsm'].get('pool_id')})
        undercloud.configure(config['undercloud']['repositories'])
        baremetal_factory.shutdown_nodes(undercloud)
        undercloud_config = provisioner.get('undercloud_config')
        if undercloud_config:
            undercloud_conf = open(undercloud_config, 'r').read()
        else:
            undercloud_conf = """
[DEFAULT]
local_ip = 192.0.2.240/24
local_interface = eth1
local_mtu = 1400
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

        # Our OpenStack default tenant are below the 1500 limit, let's ensure we won't
        # have any frame truncated.
        undercloud.set_ctlplane_mtu(1400)
        undercloud.openstack_undercloud_install()
        undercloud.enable_neutron_hack(os_username, os_password, os_project_id, os_auth_url)
        undercloud.ssh_pool.stop_all()
        exit(0)

    if step == 'overcloud':
        if undercloud.run('test -f stackrc', user='stack', ignore_error=True)[1] > 0:
            print('Run undercloud step first')
            exit(1)
        undercloud.fetch_overcloud_images(config.get('overcloud'))
        if undercloud.rhosp_version() < 10:
            undercloud.patch_ironic_ramdisk()
        undercloud.overcloud_image_upload()
        undercloud.load_instackenv()

        # the first as compute
        for node in baremetal_factory.nodes[:1]:
            undercloud.set_flavor(node, 'compute')

        # the rest is 'control' node
        for node in baremetal_factory.nodes[1:]:
            undercloud.set_flavor(node, 'control')

#        undercloud.start_overcloud_inspector()
        time.sleep(60)
        undercloud.create_file(
            '/home/stack/network-environment.yaml',
            yaml.dump({'parameter_defaults': {'DnsServers': ['8.8.8.8', '8.8.4.4']}}),
            user='stack')
        undercloud.start_overcloud_deploy(
            control_scale=1,
            compute_scale=1,
            control_flavor='control',
            compute_flavor='compute',
            environments=[
                '/home/stack/network-environment.yaml'])

        # create the public network
        undercloud.add_environment_file(
            user='stack', filename='overcloudrc')
        undercloud.run(
            'neutron net-create ext-net --shared --router:external=True',
            user='stack')
        # NOTE(Goneri): this range is from TripleO default configuration.
        undercloud.run((
            'neutron subnet-create ext-net '
            '10.0.0.0/24 '
            '--name external '
            '--allocation-pool start=10.0.0.4,end=10.0.0.250'), user='stack')
        undercloud.ssh_pool.stop_all()
        exit(0)

# This is for setuptools entry point.
main = cli
