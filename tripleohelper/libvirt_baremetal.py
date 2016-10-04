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

import tripleohelper.baremetal


class Baremetal(tripleohelper.baremetal.Baremetal):
    def __init__(self):
        pass


class BaremetalFactory(tripleohelper.baremetal.BaremetalFactory):
    def __init__(self, hypervisor=None, **kargs):
        super(BaremetalFactory, self).__init__(**kargs)
        self.hypervisor = hypervisor

    def shutdown_nodes(self, undercloud):
        self.hypervisor.run('virsh list --name|grep "baremetalbrbm"|xargs -r -n 1 virsh destroy')
