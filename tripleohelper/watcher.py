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
import multiprocessing
import time

LOG = logging.getLogger('__chainsaw__')


class Watcher(multiprocessing.Process):
    def __init__(self, undercloud, command, command_full=None):
        self.undercloud = undercloud
        self.text = command
        self.command = command
        if command_full:
            self.command = command_full
        self.stop = False
        multiprocessing.Process.__init__(self)

    def run(self):
        # we are in a new process, we should start a new SSH client
        self.undercloud.enable_user('stack')
        self.undercloud.add_environment_file(user='stack', filename='overcloudrc')
        while not self.stop:
            if self.undercloud.run(self.command, ignore_error=True, user='stack')[1] != 0:
                self.undercloud.add_annotation(
                    '%s has failed' % self.text,
                    table='watcher_failure')
            time.sleep(.5)
