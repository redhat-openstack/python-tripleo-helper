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

import datetime
import logging
import sys
import time

import rdomhelper.host0
from rdomhelper.provisioners.openstack import utils


LOG = logging.getLogger('__chainsaw__')


def build_openstack_instance(nova_api, name, image, flavor, key_name, nics):
    instance = nova_api.servers.create(
        name=name,
        image=image,
        flavor=flavor,
        key_name=key_name,
        nics=nics)

    # TODO(yassine): convert to a wait() function
    while True:
        LOG.info("instance '%s' status %s" % (name, instance.status))
        if instance.status == 'ERROR':
            LOG.error("boot instance '%s' failed" % name)
            return None
        elif instance.status == 'ACTIVE':
            LOG.info("boot  '%s' successfully" % name)
            return instance
        time.sleep(5)
        instance = nova_api.servers.get(instance.id)


def deploy_host0(os_auth_url, os_username, os_password, os_tenant_name,
                 provisioner, private_key, cleanup_environment=False):
    LOG.info("using 'openstack' provisioner")
    nova_api = utils.build_nova_api(os_auth_url, os_username,
                                    os_password, os_tenant_name)
    if cleanup_environment is True:
        utils.remove_instances_by_prefix(nova_api,
                                         provisioner['instance_name_prefix'])

    image_id_to_boot_from = utils.get_image_id(nova_api,
                                               provisioner['image']['name'])
    flavor_id = utils.get_flavor_id(nova_api, provisioner['flavor'])
    keypair_id = utils.get_keypair_id(nova_api, provisioner['keypair'])
    network_id = utils.get_network_id(nova_api, provisioner['network'])
    nics = [{'net-id': network_id}]

    instance_name = "%s-%s" % (provisioner['instance_name_prefix'],
                               str(datetime.datetime.utcnow()))
    LOG.info("building instance '%s'" % instance_name)

    instance_host0 = build_openstack_instance(
        nova_api,
        instance_name,
        image_id_to_boot_from,
        flavor_id,
        keypair_id,
        nics)

    if instance_host0:
        host0_ip = utils.add_a_floating_ip(nova_api, instance_host0)
        LOG.info("add floating ip '%s'" % host0_ip)
        utils.add_security_groups(instance_host0,
                                  provisioner['security-groups'])
        LOG.info("add security groups '%s'" %
                 provisioner['security-groups'])
        LOG.info("instance '%s' ready to use" % instance_name)
    else:
        LOG.error("instance '%s' failed" % instance_name)
        sys.exit(1)

    host0 = rdomhelper.host0.Host0(
        hostname=host0_ip,
        user=provisioner['image'].get('user', 'root'),
        key_filename=private_key)
    return host0
