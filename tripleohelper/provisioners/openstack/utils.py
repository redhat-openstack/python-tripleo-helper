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

import keystoneauth1.exceptions.connection
from keystoneauth1 import loading as ks_loading
import keystoneauth1.session
import neutronclient.v2_0
from novaclient import client as nova_client

import logging
import time

LOG = logging.getLogger('tripleohelper')


def ks_session(auth_url, username, password, project_id):
    loader = ks_loading.get_plugin_loader('password')
    auth = loader.load_from_options(auth_url=auth_url,
                                    username=username,
                                    password=password,
                                    project_id=project_id)
    sess = keystoneauth1.session.Session(auth=auth)
    return sess


def _get_id_by_attr(resources, attr, value):
    for resource in resources:
        if getattr(resource, attr) == value:
            return resource.id
    return None


def build_nova_api(sess):
    return nova_client.Client(2, session=sess)


def build_neutron_client(sess):
    return neutronclient.v2_0.client.Client(
        endpoint_url=sess.get_endpoint(service_type='network'),
        token=sess.get_token())


def get_image_id(nova_api, image_name):
    images = nova_api.images.list()
    return _get_id_by_attr(images, 'name', image_name)


def get_flavor_id(nova_api, flavor_name):
    flavors = nova_api.flavors.list()
    return _get_id_by_attr(flavors, 'name', flavor_name)


def get_keypair_id(nova_api, keypair_name):
    keypairs = nova_api.keypairs.list()
    return _get_id_by_attr(keypairs, 'name', keypair_name)


def get_network_id(nova_api, network_name):
    # NOTE(Goneri): we have a lot of temporary failure with keystone
    # this is an attempt to reduce them.
    networks = None
    for _ in range(100):
        try:
            networks = nova_api.networks.list()
        except keystoneauth1.exceptions.connection.ConnectFailure:
            time.sleep(1)
        else:
            break
    return _get_id_by_attr(networks, 'label', network_name)


def get_floating_ip(nova_api, ip=None):
    floating_ips = nova_api.floating_ips.list()
    for floating_ip in floating_ips:
        if ip and ip == floating_ip.ip:
            return floating_ip
        elif floating_ip.instance_id is None and floating_ip.fixed_ip is None:
            return floating_ip


def add_a_floating_ip(nova_api, os_instance, floating_ip=None):
    floating_ip = get_floating_ip(nova_api, floating_ip)
    os_instance.add_floating_ip(floating_ip.ip)
    LOG.info("floating ip '%s' attached to '%s'" % (floating_ip.ip, os_instance.name))
    return floating_ip.ip


def add_security_groups(os_instance, security_groups):
    for sg in security_groups:
        os_instance.add_security_group(sg)


def remove_instances_by_prefix(nova_api, prefix):
    """Remove all the instances on which their name start by a prefix."""
    for server in nova_api.servers.list():
        if server.name.startswith(prefix):
            LOG.info("Remove instance '%s'" % server.name)
            server.delete()
