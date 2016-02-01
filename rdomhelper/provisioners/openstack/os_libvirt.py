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
