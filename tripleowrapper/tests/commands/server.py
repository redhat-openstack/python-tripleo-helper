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

CREATE_STACK_USER_RUN = [
    {'error_callback': None,
     'cmd': 'adduser -m stack',
     'ignore_error': False,
     'success_status': (0, 9),
     'custom_log': None,
     'user': 'root'},
    {'error_callback': None,
     'cmd': 'mkdir -p /home/stack/.ssh',
     'ignore_error': False,
     'success_status': (0,),
     'custom_log': None,
     'user': 'root'},
    {'error_callback': None,
     'cmd': 'cp /root/.ssh/authorized_keys /home/stack/.ssh/authorized_keys',
     'ignore_error': False,
     'success_status': (0,),
     'custom_log': None,
     'user': 'root'},
    {'error_callback': None,
     'cmd': 'chown -R stack:stack /home/stack/.ssh',
     'ignore_error': False,
     'success_status': (0,),
     'custom_log': None,
     'user': 'root'},
    {'error_callback': None,
     'cmd': 'chmod 700 /home/stack/.ssh',
     'ignore_error': False,
     'success_status': (0,),
     'custom_log': None,
     'user': 'root'},
    {'error_callback': None,
     'cmd': 'chmod 600 /home/stack/.ssh/authorized_keys',
     'ignore_error': False,
     'success_status': (0,),
     'custom_log': None,
     'user': 'root'}
]

CREATE_STACK_USER_CREATE_FILE = [
    {'content': 'stack ALL=(root) NOPASSWD:ALL\n',
     'path:': '/etc/sudoers.d/stack',
     'user': 'root', 'mode': 'w'}
]

RHSM_REGISTER = [
    {'cmd': 'rm /etc/pki/product/69.pem',
     'ignore_error': True,
     'error_callback': None,
     'success_status': (0,),
     'custom_log': None,
     'user': 'root'},
    {'cmd': 'subscription-manager register --username login --password pass',
     'ignore_error': False,
     'error_callback': None,
     'success_status': (0, 64),
     'custom_log': 'subscription-manager register --username login --password *******',
     'user': 'root'},
    {'cmd': 'subscription-manager attach --auto',
     'ignore_error': False,
     'error_callback': None,
     'success_status': (0,),
     'custom_log': None,
     'user': 'root'}
]

RHSM_REGISTER_POOL_ID = RHSM_REGISTER[:2]
RHSM_REGISTER_POOL_ID.append(
    {'cmd': 'subscription-manager attach --pool pool_id',
     'ignore_error': False,
     'error_callback': None,
     'user': 'root',
     'custom_log': None,
     'success_status': (0,)}
)
