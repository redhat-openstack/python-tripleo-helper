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

import os.path
import pkg_resources

import tripleohelper


def pkg_data_filename(resource_name, filename):
    """Returns the path of a file installed along the package
    """
    resource_filename = pkg_resources.resource_filename(
        tripleohelper.__name__,
        resource_name
    )
    if filename is not None:
        resource_filename = os.path.join(resource_filename, filename)
    return resource_filename


def protect_password(password):
    return '"' + password.replace('"', '\\"') + '"'
