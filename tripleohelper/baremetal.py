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

import json


class BaremetalFactory(object):
    def __init__(self, instackenv_file=None, instackenv_content=None):
        if instackenv_file:
            with open(instackenv_file) as json_data:
                self.instackenv = json.loads(json_data)
        elif instackenv_content:
            self.instackenv = json.loads(instackenv_content)

    def initialize(self, size=2):
        """Populate the node poll.

        :param size: the number of node to create.
        """
        pass

    def get_instackenv_json(self):
        """Return the instackenv.json conent."""
        return json.dumps(self.instackenv, sort_keys=True)

    def shutdown_nodes(self, undercloud):
        undercloud.yum_install(['ipmitool'])
        print(self.instackenv)
        for i in self.instackenv:
            undercloud.run(
                ('ipmitool -I lanplus -H {pm_addr} '
                 '-U {pm_user} -P {pm_password} chassis '
                 'power off').format(
                     pm_addr=i['pm_addr'],
                     pm_user=i['pm_user'],
                     pm_password=i['pm_password']),
                success_status=(0, 1))
