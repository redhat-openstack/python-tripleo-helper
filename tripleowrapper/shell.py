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

import tripleowrapper.host0
from tripleowrapper import logger
from tripleowrapper.provisioners.openstack import os_libvirt
from tripleowrapper.provisioners.openstack import utils as os_utils
from tripleowrapper import undercloud


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

        host0 = tripleowrapper.host0.Host0(hostname=host0_ip,
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
    logger.setup_logging()
    config = yaml.load(config_file)
    ssh = config['ssh']
    host0 = None
    vm_undercloud = None

    if host0_ip:
        host0 = tripleowrapper.host0.Host0(hostname=host0_ip,
                                           user=config['provisioner']['image'].get('user', 'root'),
                                           key_filename=ssh['private_key'])
        if undercloud_ip:
            vm_undercloud = undercloud.Undercloud(undercloud_ip,
                                                  user='root',
                                                  via_ip=host0_ip,
                                                  key_filename=ssh['private_key'])
    if not host0:
        host0 = deploy_host0(os_auth_url, os_username, os_password,
                             os_tenant_name, config)

    if not vm_undercloud:
        host0.enable_repositories(config['provisioner']['repositories'])
        host0.install_nosync()
        host0.create_stack_user()
        host0.deploy_hypervisor()
        vm_undercloud = host0.instack_virt_setup(
            config['undercloud']['guest_image_path'],
            config['undercloud']['guest_image_checksum'],
            rhsm_login=config['rhsm']['login'],
            rhsm_password=config['rhsm'].get('password', os.environ.get('RHN_PW')))

    vm_undercloud.enable_repositories(config['undercloud']['repositories'])
    vm_undercloud.install_nosync()
    vm_undercloud.create_stack_user()
    vm_undercloud.install_base_packages()
    vm_undercloud.clean_system()
    vm_undercloud.update_packages()
    vm_undercloud.install_osp()
    vm_undercloud.start_overcloud()

# This is for setuptools entry point.
main = cli
