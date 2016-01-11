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

import paramiko
from paramiko import ssh_exception

import io
import logging
import select
import time

LOG = logging.getLogger('__chainsaw__')


def build_ssh_client(hostname, username, private_key):
    ssh_client = paramiko.SSHClient()
    ssh_client.load_system_host_keys()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for i in range(60):
        try:
            ssh_client.connect(hostname=hostname, username=username,
                               key_filename=private_key, allow_agent=True)
        except (ssh_exception.SSHException, OSError):
            LOG.warn("waiting for ssh service on '%s'" % hostname)
            time.sleep(1)
        else:
            return ssh_client
    return None


def run_cmd(ssh_channel, cmd):
    cmd_output = io.StringIO()
    ssh_channel.set_combine_stderr(True)
    ssh_channel.get_pty()

    LOG.info("run command '%s'" % cmd)
    ssh_channel.exec_command(cmd)

    while True:
        if ssh_channel.exit_status_ready():
            break
        rl, _, _ = select.select([ssh_channel], [], [], 30)
        if rl:
            received = ssh_channel.recv(1024).decode('UTF-8', 'ignore')
            cmd_output.write(received)
    return cmd_output.getvalue(), ssh_channel.exit_status
