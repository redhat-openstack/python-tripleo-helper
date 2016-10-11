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

import tripleohelper.host0
import tripleohelper.libvirt_baremetal
from tripleohelper import logger
from tripleohelper import undercloud


LOG = logging.getLogger('tripleohelper')


@click.command()
@click.option('--host0-ip', required=True,
              help="IP address of the hypervisor to reuse.")
@click.option('--undercloud-ip',
              help="IP address of the hypervisor to reuse.")
@click.option('--config-file', required=True, type=click.File('rb'),
              help="Chainsaw path configuration file.")
@click.argument('step', nargs=1, required=True,
                type=click.Choice(['provisioning', 'undercloud', 'overcloud', 'cleanup']))
def cli(host0_ip, undercloud_ip, config_file, step):
    config = yaml.load(config_file)
    ssh = config['ssh']
    host0 = None
    vm_undercloud = None

    print('step: %s' % step)
    logger.setup_logging()
    try:
        rhsm = config.get('rhsm')
        host0 = tripleohelper.host0.Host0(
            hostname=host0_ip,
            user='user',
            key_filename=ssh['private_key'])

        if step == 'cleanup':
            host0.teardown()
        if step == 'provisioning':
            host0.configure()
            vm_undercloud = host0.build_undercloud_on_libvirt(
                config['undercloud']['image_path'],
                rhsm=rhsm,
                repositories=config['undercloud']['repositories'])
        elif step in ['undercloud', 'overcloud']:
            undercloud_ip = host0.run("/sbin/ip n | grep $(tripleo get-vm-mac instack) | awk '{print $1;}'")[0].rstrip()
            vm_undercloud = undercloud.Undercloud(
                hostname=undercloud_ip,
                user='root',
                via_ip=host0_ip,
                key_filename=ssh['private_key'])

        if step == 'undercloud':
            vm_undercloud.configure(config['undercloud']['repositories'])
            vm_undercloud.set_ctlplane_mtu(1400)
            vm_undercloud.openstack_undercloud_install()
            vm_undercloud.fetch_overcloud_images(config.get('overcloud'))
            vm_undercloud.overcloud_image_upload()
            instackenv_content = vm_undercloud.get_file_content('instackenv.json', user='stack')
            baremetal_factory = tripleohelper.libvirt_baremetal.BaremetalFactory(
                hypervisor=host0,
                instackenv_content=instackenv_content)
            baremetal_factory.reload_environment(vm_undercloud)
            vm_undercloud.baremetal_factory = baremetal_factory
            vm_undercloud.load_instackenv()
            vm_undercloud.create_flavor('baremetal')
            for uuid in vm_undercloud.baremetal_factory.nodes:
                print('uuid: %s' % uuid)
                vm_undercloud.set_flavor(uuid, 'baremetal')
        if step == 'overcloud':
            instackenv_content = vm_undercloud.get_file_content('instackenv.json', user='stack')
            baremetal_factory = tripleohelper.libvirt_baremetal.BaremetalFactory(
                hypervisor=host0,
                instackenv_content=instackenv_content)
            baremetal_factory.reload_environment(vm_undercloud)
            vm_undercloud.baremetal_factory = baremetal_factory
            vm_undercloud.start_overcloud_deploy(control_scale=1, compute_scale=1)
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
    else:
        exit(0)

# This is for setuptools entry point.
main = cli
