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

import datetime
import logging
import os
import sys
import traceback

from dciclient.v1.api import context as dcicontext
from dciclient.v1.api import job as dcijob
from dciclient.v1.api import jobstate as dcijobstate

import rdomhelper.host0
from rdomhelper import logger
from rdomhelper.provisioners.openstack import os_libvirt
from rdomhelper.provisioners.openstack import utils as os_utils
from rdomhelper import undercloud


LOG = logging.getLogger('__chainsaw__')


def deploy_host0(os_auth_url, os_username, os_password, os_tenant_name, config):
    provisioner = config['provisioner']
    if provisioner['type'] == 'openstack':
        LOG.info("using 'openstack' provisioner")
        nova_api = os_utils.build_nova_api(os_auth_url, os_username,
                                           os_password, os_tenant_name)

        image_id_to_boot_from = os_utils.get_image_id(nova_api,
                                                      provisioner['image']['name'])
        flavor_id = os_utils.get_flavor_id(nova_api, provisioner['flavor'])
        keypair_id = os_utils.get_keypair_id(nova_api, provisioner['keypair'])
        network_id = os_utils.get_network_id(nova_api, provisioner['network'])
        nics = [{'net-id': network_id}]

        instance_name = "%s-%s" % (provisioner['instance_name_prefix'],
                                   str(datetime.datetime.utcnow()))
        LOG.info("building instance '%s'" % instance_name)

        os_instance = os_libvirt.build_openstack_instance(
            nova_api,
            instance_name,
            image_id_to_boot_from,
            flavor_id,
            keypair_id,
            nics)

        if os_instance:
            host0_ip = os_utils.add_a_floating_ip(nova_api, os_instance)
            LOG.info("add floating ip '%s'" % host0_ip)
            os_utils.add_security_groups(os_instance,
                                         provisioner['security-groups'])
            LOG.info("add security groups '%s'" %
                     provisioner['security-groups'])
            LOG.info("instance '%s' ready to use" % instance_name)
        else:
            LOG.error("instance '%s' failed" % instance_name)
            sys.exit(1)

        host0 = rdomhelper.host0.Host0(hostname=host0_ip,
                                       user=config['provisioner']['image'].get('user', 'root'),
                                       key_filename=config['ssh']['private_key'])
        host0.rhsm_register(
            config['rhsm']['login'],
            config['rhsm'].get('password', os.environ.get('RHN_PW')),
            config['rhsm']['pool_id'])
        return host0


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

    dci_context = dcicontext.build_dci_context(
        config['dci']['control_server_url'],
        config['dci']['login'],
        config['dci']['password'])
    logger.setup_logging(dci_context)

    status = 'pre-run'
    job = dcijob.schedule(dci_context,
                          remoteci_id=config['dci']['remoteci_id']).json()
    job_id = job['job']['id']

    try:
        if host0_ip:
            dcijobstate.create(dci_context, status, 'Reusing existing host0', job_id)
            host0 = rdomhelper.host0.Host0(hostname=host0_ip,
                                           user=config['provisioner']['image'].get('user', 'root'),
                                           key_filename=ssh['private_key'])
            if undercloud_ip:
                dcijobstate.create(dci_context, status, 'Reusing existing undercloud', job_id)
                vm_undercloud = undercloud.Undercloud(undercloud_ip,
                                                      user='root',
                                                      via_ip=host0_ip,
                                                      key_filename=ssh['private_key'])
        if not host0:
            dcijobstate.create(dci_context, status, 'Creating the host0', job_id)
            host0 = deploy_host0(os_auth_url, os_username, os_password,
                                 os_tenant_name, config)

        if not vm_undercloud:
            dcijobstate.create(dci_context, status, 'Creating the undercloud', job_id)
            host0.enable_repositories(config['provisioner']['repositories'])
            host0.install_nosync()
            host0.create_stack_user()
            host0.deploy_hypervisor()
            vm_undercloud = host0.instack_virt_setup(
                config['undercloud']['guest_image_path'],
                config['undercloud']['guest_image_checksum'],
                rhsm_login=config['rhsm']['login'],
                rhsm_password=config['rhsm'].get('password', os.environ.get('RHN_PW')))

        status = 'running'
        dcijobstate.create(dci_context, status, 'Configuring the undercloud', job_id)
        vm_undercloud.enable_repositories(config['undercloud']['repositories'])
        vm_undercloud.install_nosync()
        vm_undercloud.create_stack_user()
        vm_undercloud.install_base_packages()
        vm_undercloud.clean_system()
        vm_undercloud.update_packages()
        vm_undercloud.install_osp()
        vm_undercloud.start_undercloud(
            config['undercloud']['guest_image_path'],
            config['undercloud']['guest_image_checksum'],
            config['undercloud']['files'],
        )
        vm_undercloud.start_overcloud()
        vm_undercloud.run_tempest()
        dcijobstate.create(dci_context, 'success', 'Job succeed :-)', job_id)
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
        dcijobstate.create(dci_context, 'failure', 'Job failed :-(', job_id)
        raise e

# This is for setuptools entry point.
main = cli
