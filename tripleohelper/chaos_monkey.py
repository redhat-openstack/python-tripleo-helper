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

import logging
import threading
import time

LOG = logging.getLogger('tripleohelper')


class ChaosMonkey(threading.Thread):
    def __init__(self):
        self._nodes = []
        self.stop = False
        self.down_duration = 60
        self.up_duration = 600
        threading.Thread.__init__(self)

    def add_node(self, node):
        LOG.debug('add node %s in ChaosMonkey pool' % node.name)
        self._nodes.append(node)

    def run(self):
        while not self.stop:
            for bm_node in self._nodes:
                LOG.debug('Disconnecting node %s for %d seconds' % (bm_node.name, self.down_duration))
                bm_node.admin_state_up(False)
                time.sleep(self.down_duration)
                LOG.debug('Reconnecting node %s for %d seconds' % (bm_node.name, self.up_duration))
                bm_node.admin_state_up(True)
                time.sleep(self.up_duration)
