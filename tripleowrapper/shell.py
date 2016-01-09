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

from tripleowrapper.provisioners.openstack import os_libvirt
from tripleowrapper.provisioners.openstack import utils as os_utils


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
    if provisioner['type'] == 'openstack':
        print("* Using 'openstack' provisioner.")
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
        print("* Building instance %s\n" % instance_name)

        os_instance = os_libvirt.build_openstack_instance(
            nova_api,
            instance_name,
            image_id_to_boot_from,
            flavor_id,
            keypair_id,
            nics)

        if os_instance:
            floating_ip = os_utils.add_a_floating_ip(nova_api, os_instance)
            print("* Added floating ip %s" % floating_ip)
            os_utils.add_security_groups(os_instance,
                                         provisioner['security-groups'])
            print("* Added security groups %s" %
                  provisioner['security-groups'])
            print("* VM %s ready to use" % instance_name)
        else:
            print("* VM %s failed" % instance_name)
    else:
        print("Unknown provisioner %s" % provisioner['type'])


# This is for setuptools entry point.
main = cli
