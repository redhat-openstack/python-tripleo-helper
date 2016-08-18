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

import logging
import time

import novaclient.exceptions

LOG = logging.getLogger('tripleohelper')


def build_openstack_instance(nova_api, name, image, flavor, key_name, nics):
    LOG.info("building instance '%s'" % name)

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


def add_provision_security_group(nova_api):
    try:
        group = nova_api.security_groups.find(name='provision')
    except novaclient.exceptions.NotFound:
        group = nova_api.security_groups.create(name='provision', description='Provision network')
        nova_api.security_group_rules.create(group.id, ip_protocol="icmp", from_port=-1, to_port=-1, cidr='0.0.0.0/0')
        nova_api.security_group_rules.create(group.id, ip_protocol="tcp", from_port=1, to_port=65535, cidr='0.0.0.0/0')
        nova_api.security_group_rules.create(group.id, ip_protocol="udp", from_port=1, to_port=65535, cidr='0.0.0.0/0')
    return group
