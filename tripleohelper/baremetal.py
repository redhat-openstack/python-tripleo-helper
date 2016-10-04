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

import tripleohelper.server as server

import json


class Baremetal(server.Server):
    """A baremetal node."""
    def __init__(self):
        server.Server.__init__(self, None)
        self.mac = None
        self.name = None


class BaremetalFactory(object):
    def __init__(self, instackenv_file=None, instackenv_content=None):
        if instackenv_file:
            with open(instackenv_file) as json_data:
                self.instackenv = json.loads(json_data)
        elif instackenv_content:
            self.instackenv = json.loads(instackenv_content)
        self.nodes = []

    def initialize(self, size=2):
        """Populate the node poll.

        :param size: the number of node to create.
        """
        pass

    def get_instackenv_json(self):
        """Return the instackenv.json conent."""
        return json.dumps(self.instackenv, sort_keys=True)

    def load_instackenv_content(self, undercloud):
        instackenv_content = undercloud.get_file_content(
            'instackenv.json', user='stack')
        return json.loads(instackenv_content)

    def reload_environment(self, undercloud):
        instackenv = self.load_instackenv_content(undercloud)
        if 'nodes' in instackenv:
            node_list = instackenv['nodes']
        else:
            node_list = instackenv
        for instack_node in node_list:
            print(instack_node)
            node = Baremetal()
            node.mac = instack_node['mac'][0]
            self.nodes.append(node)
        # restore the flavor
        undercloud.add_environment_file(user='stack', filename='stackrc')
        command = """ironic node-list --fields properties|sed -n 's/.*profile:\([-_a-z]*\),.*/\\1/p'"""
        flavor_list = undercloud.run(command, user='stack')[0].split()
        if flavor_list:
            i = iter(flavor_list)
            for node in self.nodes:
                node.flavor = next(i)
        self.set_ironic_uuid(undercloud.list_nodes())

    def shutdown_nodes(self, undercloud):
        undercloud.yum_install(['ipmitool'])
        for i in self.instackenv:
            undercloud.run(
                ('ipmitool -I lanplus -H {pm_addr} '
                 '-U {pm_user} -P {pm_password} chassis '
                 'power off').format(
                     pm_addr=i['pm_addr'],
                     pm_user=i['pm_user'],
                     pm_password=i['pm_password']),
                success_status=(0, 1))

    def set_ironic_uuid(self, uuid_list):
        """Map a list of Ironic UUID to BM nodes.
        """
        # TODO(Gonéri): ensure we adjust the correct node
        i = iter(self.nodes)
        for uuid in uuid_list:
            node = next(i)
            node.uuid = uuid
