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
import paramiko.ssh_exception
import time
import yaml

import logging

import rdomhelper.chaos_monkey
from rdomhelper import logger
from rdomhelper import ovb_baremetal
from rdomhelper import ovb_undercloud
from rdomhelper.provisioners.openstack import utils as os_utils
import rdomhelper.undercloud
import rdomhelper.watcher

import neutronclient.common.exceptions
import neutronclient.v2_0.client

LOG = logging.getLogger('__chainsaw__')


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
@click.option('--os-tenant-name', envvar='OS_TENANT_NAME', required=True,
              help="Openstack tenant name.")
@click.option('--undercloud-ip', required=False,
              help="IP address of an undercloud to reuse.")
@click.option('--config-file', required=True, type=click.File('rb'),
              help="Chainsaw path configuration file.")
def cli(os_auth_url, os_username, os_password, os_tenant_name, undercloud_ip, config_file):
    config = yaml.load(config_file)
    logger.setup_logging(config_file='/tmp/ovb.log')
    undercloud = None
    baremetal_factory = None

    neutron = neutronclient.v2_0.client.Client(username=os_username,
                                               password=os_password,
                                               tenant_name=os_tenant_name,
                                               auth_url=os_auth_url)
    nova_api = os_utils.build_nova_api(os_auth_url, os_username,
                                       os_password, os_tenant_name)

    if undercloud_ip:
        undercloud = rdomhelper.undercloud.Undercloud(
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
    else:
        purge_existing_ovb(nova_api, neutron)
        initialize_network(neutron)
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
        undercloud.configure(config['undercloud']['repositories'])

        undercloud.install_collectd()
        undercloud.install_grafana()
        undercloud.add_annotation('Downloading overcloud images')
        undercloud.fetch_overcloud_images(config['overcloud'])
        undercloud.inject_collectd('overcloud-full.qcow2')

        baremetal_factory = ovb_baremetal.BaremetalFactory(
            nova_api,
            neutron,
            keypair=config['provisioner']['keypair'],
            key_filename=config['ssh']['private_key'],
            security_groups=config['provisioner']['security-groups'],
            os_params={'os_username': os_username,
                       'os_password': os_password,
                       'os_tenant_name': os_tenant_name,
                       'os_auth_url': os_auth_url})
        undercloud.add_annotation('Creating the Baremetal VMs')
        baremetal_factory.initialize(size=7)
        baremetal_factory.shutdown_nodes(undercloud)
        undercloud.create_file(
            'instackenv.json',
            baremetal_factory.get_instackenv_json(), user='stack')
    if undercloud.run('test -f stackrc', user='stack', ignore_error=True)[1] > 0:
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

        # Our OpenStack default tenant are below the 1500 limit, let's ensure we won't
        # have any frame truncated.
        undercloud.set_ctlplane_mtu(1400)
        undercloud.add_annotation('openstack undercloud install')
        undercloud.openstack_undercloud_install(
            config['undercloud']['image_path'],
            config['undercloud']['image_checksum'])
        undercloud.enable_neutron_hack(os_username, os_password, os_tenant_name, os_auth_url)

    if undercloud.run('test -f overcloudrc', user='stack', ignore_error=True)[1] > 0:
        undercloud.add_annotation('openstack image upload')
        undercloud.overcloud_image_upload()
        undercloud.load_instackenv()

        # register the ironic UUID, this should be done directly in load_instackenv()
        baremetal_factory.set_ironic_uuid(undercloud.list_nodes())

        # two first as compute
        for node in baremetal_factory.nodes[:1]:
            undercloud.set_flavor(node, 'compute')

        # the rest is 'control' node
        for node in baremetal_factory.nodes[1:]:
            undercloud.set_flavor(node, 'control')

        undercloud.add_annotation('openstack overcloud inspector')
        for bm_node in baremetal_factory.nodes:
            bm_node.pxe_netboot(filename='inspector.ipxe')
        undercloud.start_overcloud_inspector()

        # if ipxe is frozen, the VM will stay running.
        # https://bugzilla.redhat.com/show_bug.cgi?id=1310778
        baremetal_factory.shutdown_nodes(undercloud)
        for bm_node in baremetal_factory.nodes:
            bm_node.pxe_netboot(filename='boot.ipxe')
        undercloud.create_file(
            '/home/stack/network-environment.yaml',
            yaml.dump({'parameter_defaults': {'DnsServers': ['8.8.8.8', '8.8.4.4']}}),
            user='stack')
        # Allow access to influxdb from the subnet
        undercloud.run('iptables -I INPUT -s 192.0.2.0/24 -p udp -m multiport --dports 25826 -j ACCEPT')
        undercloud.add_annotation('openstack overcloud deploy')
        undercloud.start_overcloud_deploy(
            control_scale=3,
            compute_scale=1,
            control_flavor='control',
            compute_flavor='compute',
            environments=[
                '/home/stack/network-environment.yaml',
                '/usr/share/openstack-tripleo-heat-templates/environments/puppet-pacemaker.yaml'])
        undercloud.add_annotation('overcloud is ready')

    undercloud.install_rally()
    for bm_node in baremetal_factory.nodes:
        bm_node.refresh_status(undercloud)
    chaos = rdomhelper.chaos_monkey.ChaosMonkey()
    for node in baremetal_factory.nodes:
        if node.flavor == 'control' and node._os_instance.status == 'ACTIVE':
            chaos.add_node(node)
    watchers = [
        rdomhelper.watcher.Watcher(undercloud, 'nova list'),
        rdomhelper.watcher.Watcher(undercloud, 'glance image-list'),
        rdomhelper.watcher.Watcher(undercloud, 'neutron port-list'),
        rdomhelper.watcher.Watcher(undercloud, 'neutron subnet-list'),
        rdomhelper.watcher.Watcher(undercloud, 'rally (create-and-delete-stack_with_volume)', 'cd /home/stack/rally/samples/tasks/scenarios/heat && rally task start --task create-and-delete-stack_with_volume.json >> /tmp/rally_deployment_run.log 2>&1'),
    ]
    for w in watchers:
        w.start()

    # all controller will be, one by one, down 120s then up 120s
    chaos.down_duration = 1
    chaos.up_duration = 600
    success = True
    try:
        chaos.start()
        undercloud.add_annotation('start chaos monkey')

        time.sleep(300)

        undercloud.add_annotation('add new controller - 4')
        undercloud.start_overcloud_deploy(
            control_scale=4,
            compute_scale=1,
            control_flavor='control',
            compute_flavor='compute',
            environments=[
                '/home/stack/network-environment.yaml',
                '/usr/share/openstack-tripleo-heat-templates/environments/puppet-pacemaker.yaml'])
        undercloud.add_annotation('controller added')

        time.sleep(300)

        undercloud.add_annotation('add new controller - 5')
        undercloud.start_overcloud_deploy(
            control_scale=5,
            compute_scale=1,
            control_flavor='control',
            compute_flavor='compute',
            environments=[
                '/home/stack/network-environment.yaml',
                '/usr/share/openstack-tripleo-heat-templates/environments/puppet-pacemaker.yaml'])
        undercloud.add_annotation('controller added')

        time.sleep(300)

        undercloud.add_annotation('add new controller - 6')
        undercloud.start_overcloud_deploy(
            control_scale=5,
            compute_scale=1,
            control_flavor='control',
            compute_flavor='compute',
            environments=[
                '/home/stack/network-environment.yaml',
                '/usr/share/openstack-tripleo-heat-templates/environments/puppet-pacemaker.yaml'])
        undercloud.add_annotation('controller added')
    except paramiko.ssh_exception.SSHException as e:
        LOG.exception(e)
        success = False
    finally:
        time.sleep(300)
        chaos.stop = True
        for w in watchers:
            w.terminate()
    LOG.info('success: %s' % success)
    undercloud.add_annotation('final status: %s' % success)

# This is for setuptools entry point.
main = cli
