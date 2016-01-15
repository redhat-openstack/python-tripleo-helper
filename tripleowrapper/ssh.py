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


class SshClient(object):
    """SSH client based on Paramiko.

    This class implements the following features:
        - run commands on a remote host
        - send file to a remote host
        - redirect connection to another ssh server so that every commands will
        be executed on the redirected host
        - send files
        - create remote files
    """
    def __init__(self, hostname, user, key_filename=None,
                 redirect_to_host=None):
        """:param hostname: the host on which to connect
        :type hostname: str
        :param user: the user to use for the connection
        :type user: str
        :param key_filename: the private key path to use, by default it will
        use the system host keys
        :type key_filename: str
        :param redirect_to_host: the host on which to redirect, by default it
        will use the port 22
        :type redirect_to_host: str
        """
        self._hostname = hostname
        self._user = user
        self._key_filename = key_filename
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._redirect_to_host = redirect_to_host
        self._transport = None
        self._started = False

    def start(self):
        """Start the ssh client and connect to the host.

        It will wait until the ssh service is available during 90 seconds.
        If it doesn't succed to connect then the function will raise
        an SSHException.
        """
        proxy = None
        for i in range(90):
            try:
                if self._redirect_to_host:
                    proxy = paramiko.ProxyCommand(
                        'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -W %s:%s %s@%s' %
                        (self._redirect_to_host, 22, self._user, self._hostname))
                self._client.connect(hostname=self._hostname,
                                     username=self._user,
                                     key_filename=self._key_filename,
                                     allow_agent=True,
                                     sock=proxy)
            except (ssh_exception.SSHException,
                    ssh_exception.NoValidConnectionsError,
                    OSError,
                    TypeError) as e:
                LOG.debug("exception: '%s'" % str(e))
                LOG.warn("waiting for ssh service on '%s@%s' %s" %
                         (self._user, self._hostname, self._redirect_to_host))
                time.sleep(1)
            else:
                self._transport = self._client.get_transport()
                self._started = True
                return
        _error = ("unable to connect to ssh service on '%s'" % self._hostname)
        LOG.error(_error)
        raise ssh_exception.SSHException(_error)

    def _check_started(self):
        if not self._started:
            _error = "ssh client not started, please start the client"
            LOG.error(_error)
            raise ssh_exception.SSHException(_error)

    def stop(self):
        """Close the ssh connection."""
        self._started = False
        self._client.close()

    def run(self, cmd, sudo=False, ignore_error=False, success_status=(0,),
            error_callback=None):
        """Run a command on the remote host.

        The command is run on the remote host, if there is a redirected host
        then the command will be run on that redirected host. See __init__.

        :param cmd: the command to run
        :type cmd: str
        :param success_status: the list of the possible success status
        :type success_status: list
        :param error_callback: if provided, the callback to call in case of
        a failure. it will be called with two args, the output of the command
        and the returned error code.
        :return: the tuple (output of the command, returned code)
        :rtype: tuple
        """
        self._check_started()
        cmd_output = io.StringIO()
        channel = self._get_channel()
        cmd = "sudo %s" % cmd if sudo else cmd
        if self._redirect_to_host:
            LOG.info("[%s@%s] run '%s'" % (self._user,
                                           self._redirect_to_host, cmd))
        else:
            LOG.info("[%s@%s] run '%s'" % (self._user, self._hostname, cmd))
        channel.exec_command(cmd)

        while True:
            if channel.exit_status_ready():
                break
            rl, _, _ = select.select([channel], [], [], 30)
            if rl:
                received = channel.recv(1024).decode('UTF-8', 'ignore').strip()
                if received:
                    LOG.debug(received)
                    cmd_output.write(received)
        cmd_output = cmd_output.getvalue()
        exit_status = channel.exit_status

        if ignore_error or channel.exit_status in success_status:
            return cmd_output, channel.exit_status
        elif error_callback:
            return error_callback(cmd_output, exit_status)
        else:
            _err_hostname = self._redirect_to_host or self._hostname
            _error = ("error on command '%s' on '%s', result='%s', rc='%s'" %
                      (cmd, _err_hostname, cmd_output, exit_status))
            LOG.error(_error)
            raise ssh_exception.SSHException(_error)

    def _get_channel(self):
        """Returns a channel according to if there is a redirection to do or
        not.
        """
        channel = self._transport.open_session()
        channel.set_combine_stderr(True)
        channel.get_pty()
        return channel

    def send_file(self, local_path, remote_path):
        """Send a file to the remote host.
        :param local_path: the local path of the file
        :type local_path: str
        :param remote_path: the remote path of the file
        :type remote_path: str
        :return: the file attributes
        :rtype: paramiko.sftp_attr.SFTPAttributes
        """
        self._check_started()
        sftp = paramiko.SFTPClient.from_transport(self._transport)
        return sftp.put(local_path, remote_path)

    def create_file(self, path, content, mode='w'):
        """Create a file with a content.
        :param path: the path of the file.
        :type path: str
        :param content: the content of the file
        :type content: str
        :param mode: the mode of the file while opening it
        :type mode: str
        """
        self._check_started()
        sftp = paramiko.SFTPClient.from_transport(self._transport)
        with sftp.open(path, mode) as remote_file:
            remote_file.write(content)
            remote_file.flush()

    def info(self):
        return {'hostname': self._hostname,
                'user': self._user,
                'key_filename': self._key_filename}


class PoolSshClient(object):
    def __init__(self):
        self._ssh_clients = {}

    def build_ssh_client(self, hostname, user, key_filename=None,
                         redirect_to_host=None):
        _ssh_client = SshClient(hostname, user, key_filename,
                                redirect_to_host)
        _ssh_client.start()
        self._ssh_clients[user] = _ssh_client

    def add_ssh_client(self, user, ssh_client):
        self._ssh_clients[user] = ssh_client

    def del_ssh_client(self, user):
        self._check_ssh_client(user)
        del self._ssh_clients[user]

    def get_client(self, user):
        self._check_ssh_client(user)
        return self._ssh_clients[user]

    def _check_ssh_client(self, user):
        if user not in self._ssh_clients.keys():
            _error = "ssh client for user %s not existing" % user
            LOG.error(_error)
            raise ssh_exception.SSHException(_error)

    def run(self, user, cmd, sudo=False, ignore_error=False,
            success_status=(0,), error_callback=None):
        self._check_ssh_client(user)

        return self._ssh_clients[user].run(
            cmd,
            sudo=sudo,
            ignore_error=ignore_error,
            success_status=success_status,
            error_callback=error_callback)

    def send_file(self, user, local_path, remote_path):
        self._check_ssh_client(user)
        return self._ssh_clients[user].send_file(local_path, remote_path)

    def create_file(self, user, path, content, mode='w'):
        self._check_ssh_client(user)
        return self._ssh_clients[user].create_file(path, content, mode)

    def stop_all(self):
        for ssh_client in self._ssh_clients.values():
            ssh_client.stop()
