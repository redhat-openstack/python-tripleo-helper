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
import os
import select
import socket
import time

LOG = logging.getLogger('tripleohelper')


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
                 via_ip=None):
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
        assert hostname, 'hostname is defined.'
        assert user, 'user is defined.'
        self._hostname = hostname
        self._user = user
        self._key_filename = key_filename
        self.load_private_key(key_filename)
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.via_ip = via_ip
        self._transport = None
        self._started = False
        self.description = 'not started yet'
        self._environment_filenames = []

    def load_private_key(self, priv_key):
        """Register the SSH private key."""
        with open(priv_key) as fd:
            self._private_key = paramiko.RSAKey.from_private_key(fd)

    def _get_transport_via_ip(self):
        for i in range(60):
            try:
                channel = self._client.get_transport().open_channel(
                    'direct-tcpip',
                    (self._hostname, 22),
                    (self.via_ip, 0))
            except ssh_exception.ChannelException:
                LOG.debug('%s creating the direct-tcip connections' % self.description)
                time.sleep(1)
            else:
                transport = paramiko.Transport(channel)
                transport.start_client()
                transport.auth_publickey(self._user, self._private_key)
                return transport
        raise Exception()

    def _get_transport(self):
        if self.via_ip:
            transport = self._get_transport_via_ip()
        else:
            transport = self._client.get_transport()
        transport.set_keepalive(10)
        return transport

    def start(self):
        """Start the ssh client and connect to the host.

        It will wait until the ssh service is available during 90 seconds.
        If it doesn't succed to connect then the function will raise
        an SSHException.
        """
        if self.via_ip:
            connect_to = self.via_ip
            self.description = '[%s@%s via %s]' % (self._user,
                                                   self._hostname,
                                                   self.via_ip)
        else:
            connect_to = self._hostname
            self.description = '[%s@%s]' % (self._user,
                                            self._hostname)

        for i in range(60):
            try:
                self._client.connect(
                    connect_to,
                    username=self._user,
                    allow_agent=True,
                    key_filename=self._key_filename)
            # NOTE(Gonéri): TypeError is in the list because of
            # https://github.com/paramiko/paramiko/issues/615
                self._transport = self._get_transport()
            except (OSError,
                    TypeError,
                    ssh_exception.SSHException,
                    ssh_exception.NoValidConnectionsError):
                LOG.info('%s waiting for %s' % (self.description, connect_to))
                # LOG.debug("exception: '%s'" % str(e))
                time.sleep(1)
            else:
                LOG.debug('%s connected' % self.description)
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

    def _prepare_cmd(self, cmd, sudo=False):
        if sudo:
            cmd = "sudo %s" % cmd
        else:
            for filename in self._environment_filenames:
                cmd = '. %s; %s' % (filename, cmd)
        return cmd

    def run(self, cmd, sudo=False, ignore_error=False, success_status=(0,),
            error_callback=None, custom_log=None, retry=0):
        """Run a command on the remote host.

        The command is run on the remote host, if there is a redirected host
        then the command will be run on that redirected host. See __init__.

        :param cmd: the command to run
        :type cmd: str
        :param sudo: True if the command should be run with sudo, this parameter
        disable the use of environment files.
        :type sudo: str
        :param success_status: the list of the possible success status
        :type success_status: list
        :param error_callback: if provided, the callback to call in case of
        a failure. it will be called with two args, the output of the command
        and the returned error code.
        :return: the tuple (output of the command, returned code)
        :rtype: tuple
        :param custom_log: a optional string to record in the log instead of the command.
        This is useful for example if you want to hide a password.
        :type custom_log: str
        """
        self._check_started()
        cmd_output = io.StringIO()
        channel = self._get_channel()
        cmd = self._prepare_cmd(cmd, sudo=sudo)

        if not custom_log:
            custom_log = cmd
        LOG.info("%s run '%s'" % (self.description, custom_log))
        channel.exec_command(cmd)

        while True:
            received = None
            rl, _, _ = select.select([channel], [], [], 30)
            if rl:
                received = channel.recv(1024).decode('UTF-8', 'ignore').strip()
                if received:
                    LOG.debug(received)
                    cmd_output.write(received)
            if channel.exit_status_ready() and not received:
                break
        cmd_output = cmd_output.getvalue()
        exit_status = channel.exit_status
        try:
            return self._evaluate_run_result(
                exit_status, cmd_output, ignore_error=ignore_error,
                success_status=success_status, error_callback=error_callback,
                custom_log=custom_log)
        except (paramiko.ssh_exception.SSHException, socket.error) as e:
            if not retry:
                raise e
            else:
                return self.run(
                    cmd, sudo=sudo, ignore_error=ignore_error,
                    success_status=success_status,
                    error_callback=error_callback, custom_log=custom_log,
                    retry=(retry - 1))

    def _evaluate_run_result(
            self, exit_status, cmd_output, ignore_error=False, success_status=(0,),
            error_callback=None, custom_log=None):

        if ignore_error or exit_status in success_status:
            return cmd_output, exit_status
        elif error_callback:
            return error_callback(cmd_output, exit_status)
        else:
            _error = ("%s command %s has failed with, rc='%s'" %
                      (self.description, custom_log, exit_status))
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

    def send_file(self, local_path, remote_path, unix_mode=None):
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
        sftp.put(local_path, remote_path)
        if unix_mode:
            sftp.chmod(remote_path, unix_mode)

    def send_dir(self, local_path, remote_path):
        """Send a directory to the remote host.
        :param local_path: the local path of the directory
        :type local_path: str
        :param remote_path: the remote path of the directory
        :type remote_path: str
        :return: the file attributes
        :rtype: paramiko.sftp_attr.SFTPAttributes
        """
        directory, parent = os.path.split(local_path)
        os.chdir(directory)
        self._check_started()
        sftp = paramiko.SFTPClient.from_transport(self._transport)
        for walker in os.walk(parent):
            try:
                sftp.mkdir(os.path.join(remote_path, walker[0]))
            except Exception:
                LOG.info('directory %s exists' % walker[0])
            for file in walker[2]:
                sftp.put(os.path.join(walker[0], file),
                         os.path.join(remote_path, walker[0], file))

    def open(self, filename, mode='r'):
        self._check_started()
        sftp = paramiko.SFTPClient.from_transport(self._transport)
        return sftp.open(filename, mode)

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

    def add_environment_file(self, filename):
        if filename not in self._environment_filenames:
            self._environment_filenames.append(filename)


class PoolSshClient(object):
    def __init__(self):
        self._ssh_clients = {}

    def build_ssh_client(self, hostname, user, key_filename=None,
                         via_ip=None):
        _ssh_client = SshClient(hostname, user, key_filename,
                                via_ip)
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
            success_status=(0,), error_callback=None, custom_log=None,
            retry=0):
        self._check_ssh_client(user)

        return self._ssh_clients[user].run(
            cmd,
            sudo=sudo,
            ignore_error=ignore_error,
            success_status=success_status,
            error_callback=error_callback,
            custom_log=custom_log,
            retry=retry)

    def send_file(self, user, local_path, remote_path, unix_mode=None):
        self._check_ssh_client(user)
        return self._ssh_clients[user].send_file(local_path, remote_path, unix_mode)

    def send_dir(self, user, local_path, remote_path):
        self._check_ssh_client(user)
        return self._ssh_clients[user].send_dir(local_path, remote_path)

    def open(self, user, filename, mode='r'):
        self._check_ssh_client(user)
        return self._ssh_clients[user].open(filename, mode)

    def create_file(self, user, path, content, mode='w'):
        self._check_ssh_client(user)
        return self._ssh_clients[user].create_file(path, content, mode)

    def stop_all(self):
        for ssh_client in self._ssh_clients.values():
            ssh_client.stop()
        self._ssh_clients = {}

    def add_environment_file(self, user, filename):
        self._check_ssh_client(user)

        self._ssh_clients[user].add_environment_file(filename)
