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
import yaml

import logging
import traceback

import tripleohelper.baremetal
import tripleohelper.host0
from tripleohelper import logger
from tripleohelper.provisioners.openstack import provisioner as os_provisioner
from tripleohelper import undercloud


LOG = logging.getLogger('__chainsaw__')


@click.command()
@click.option('--os-auth-url', envvar='OS_AUTH_URL', required=True,
              help="Keystone auth url.")
@click.option('--os-username', envvar='OS_USERNAME', required=True,
              help="Openstack username account.")
@click.option('--os-password', envvar='OS_PASSWORD', required=True,
              help="Openstack password account.")
@click.option('--os-tenant-name', envvar='OS_TENANT_NAME', required=True,
              help="Openstack tenant name.")
@click.option('--host0-ip', required=False,
              help="IP address of a host0 to reuse.")
@click.option('--undercloud-ip', required=False,
              help="IP address of an undercloud to reuse.")
@click.option('--config-file', required=True, type=click.File('rb'),
              help="Chainsaw path configuration file.")
def cli(os_auth_url, os_username, os_password, os_tenant_name, host0_ip, undercloud_ip, config_file):
    config = yaml.load(config_file)
    ssh = config['ssh']
    host0 = None
    vm_undercloud = None

    logger.setup_logging()
    try:
        rhsm = config.get('rhsm')
        if host0_ip:
            host0 = tripleohelper.host0.Host0(hostname=host0_ip,
                                              user=config['provisioner']['image'].get('user', 'root'),
                                              key_filename=ssh['private_key'])
        else:
            host0 = os_provisioner.deploy_host0(os_auth_url, os_username,
                                                os_password, os_tenant_name,
                                                config['provisioner'],
                                                config['ssh']['private_key'])
        host0.configure(rhsm=rhsm,
                        repositories=config['host0']['repositories'])

        if undercloud_ip:
            vm_undercloud = undercloud.Undercloud(hostname=undercloud_ip,
                                                  user='root',
                                                  via_ip=host0_ip,
                                                  key_filename=ssh['private_key'])
        else:
            vm_undercloud = host0.build_undercloud_on_libvirt(
                config['undercloud']['image_path'],
                config['undercloud']['image_checksum'],
                rhsm=rhsm)

        vm_undercloud.configure(config['undercloud']['repositories'])
        vm_undercloud.set_ctlplane_mtu(1400)
        vm_undercloud.openstack_undercloud_install(
            config['undercloud']['image_path'],
            config['undercloud']['image_checksum'])

        vm_undercloud.fetch_overcloud_images(config['overcloud'])
        vm_undercloud.overcloud_image_upload()
        vm_undercloud.baremetal_factory = tripleohelper.baremetal.BaremetalFactory(
            vm_undercloud.get_file_content('instackenv.json'))
        vm_undercloud.load_instackenv()
        vm_undercloud.create_flavor('baremetal')
        for uuid in vm_undercloud.list_nodes():
            vm_undercloud.set_flavor(uuid, 'baremetal')
        vm_undercloud.start_overcloud_deploy(control_scale=1, compute_scale=1)
        vm_undercloud.run_tempest()
    except Exception as e:
        if host0:
            LOG.info('___________')
            cmd = 'You can start from you current possition with the following command: '
            cmd += 'chainsaw --config-file %s --host0-ip %s' % (config_file.name, host0.hostname)
            if vm_undercloud:
                cmd += ' --undercloud-ip %s' % vm_undercloud.hostname
            LOG.info(cmd)
            LOG.info('___________')
        LOG.error(traceback.format_exc())
        raise e

# This is for setuptools entry point.
main = cli
