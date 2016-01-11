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
from tripleowrapper.provisioners.openstack import os_libvirt
from tripleowrapper.provisioners.openstack import utils as os_utils
from tripleowrapper import ssh_utils

LOG = logging.getLogger('__chainsaw__')


def setup_logging():
    logger = logging.getLogger('__chainsaw__')
    logger.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    try:
        import colorlog
        formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s :: %(levelname)s :: %(message)s",
            datefmt=None,
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red'
            }
        )
        stream_handler.setFormatter(formatter)
    except ImportError:
        pass
    logger.addHandler(stream_handler)

setup_logging()


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
    provisioner = config['provisioner']
    ssh = config['ssh']
    if provisioner['type'] == 'openstack':
        LOG.info("using 'openstack' provisioner")
        nova_api = os_utils.build_nova_api(os_auth_url, os_username,
                                           os_password, os_tenant_name)

        image_id_to_boot_from = os_utils.get_image_id(nova_api,
                                                      provisioner['image'])
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
            floating_ip = os_utils.add_a_floating_ip(nova_api, os_instance)
            LOG.info("add floating ip '%s'" % floating_ip)
            os_utils.add_security_groups(os_instance,
                                         provisioner['security-groups'])
            LOG.info("add security groups '%s'" %
                     provisioner['security-groups'])
            LOG.info("instance '%s' ready to use" % instance_name)
            ssh_client = ssh_utils.build_ssh_client(floating_ip,
                                                    ssh['username'],
                                                    ssh['private_key'])
            with ssh_client.get_transport() as transport:
                channel = transport.open_session()
                result, status = ssh_utils.run_cmd(channel, "uname -a")
                LOG.info("* result '%s', status '%s'" % (result, status))
            ssh_client.close()
        else:
            LOG.error("instance '%s' failed" % instance_name)
            exit(1)

        host0 = tripleowrapper.host0.Host0(floating_ip)
        host0.enable_nosync()
        host0.set_rhsn_credentials(
            config['rhsm']['login'],
            config['rhsm'].get('password', os.environ['RHN_PW']),
            config['rhsm']['pool_id'])
        host0.enable_repositories(provisioner['repositories'])
        undercloud = host0.instack_virt_setup(
            provisioner['undercloud']['guest_image_path'],
            provisioner['undercloud']['guest_image_checksum'])
        print(host0)
        print(undercloud)
    else:
        LOG.error("unknown provisioner '%s'" % provisioner['type'])


# This is for setuptools entry point.
main = cli
