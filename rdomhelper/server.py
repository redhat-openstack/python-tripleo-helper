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

from rdomhelper import ssh

LOG = logging.getLogger('__chainsaw__')


class Server(object):
    def __init__(self, hostname, user='root', via_ip=None, key_filename=None,
                 redirect_to_host=None):
        self.hostname = hostname
        self._key_filename = key_filename
        self._via_ip = via_ip
        self._ssh_pool = ssh.PoolSshClient()
        self._redirect_to_host = redirect_to_host
        self.__enable_root_user(user)

    def __enable_root_user(self, user):
        """Enable the root account on the remote host."""

        _root_ssh_client = ssh.SshClient(
            hostname=self.hostname,
            user='root',
            key_filename=self._key_filename,
            via_ip=self._via_ip)

        if user == 'root':
            # connect as a root user
            _root_ssh_client.start()
            result, _ = _root_ssh_client.run('uname -a')

            # check if root is not allowed
            if 'Please login as the user "cloud-user"' in result:
                image_user = 'cloud-user'
                _root_ssh_client.stop()
            else:
                self._ssh_pool.add_ssh_client('root', _root_ssh_client)
                return
        else:
            image_user = user

        LOG.info('enabling the root user')
        # add the cloud user to the ssh pool
        self._ssh_pool.build_ssh_client(
            hostname=self.hostname,
            user=image_user,
            key_filename=self._key_filename,
            via_ip=self._via_ip)
        # enable the root user
        _cmd = "sudo sed -i 's,.*ssh-rsa,ssh-rsa,' /root/.ssh/authorized_keys"
        self._ssh_pool.run(image_user, _cmd)

        # add the root user to the ssh pool
        _root_ssh_client.start()
        self._ssh_pool.add_ssh_client('root', _root_ssh_client)

    def send_file(self, local_path, remote_path, user='root'):
        return self._ssh_pool.send_file(user, local_path, remote_path)

    def create_file(self, path, content, mode='w', user='root'):
        return self._ssh_pool.create_file(user, path, content, mode)

    def run(self, cmd, user='root', sudo=False, ignore_error=False,
            success_status=(0,), error_callback=None, custom_log=None):
        return self._ssh_pool.run(
            user, cmd, sudo=sudo, ignore_error=ignore_error,
            success_status=success_status, error_callback=error_callback,
            custom_log=custom_log)

    def install_nosync(self):
        _, rc = self.run('yum install -y https://kojipkgs.fedoraproject.org/packages/nosync/1.0/1.el7/x86_64/nosync-1.0-1.el7.x86_64.rpm',
                         ignore_error=True)
        if rc == 0:
            self.run('echo /usr/lib64/nosync/nosync.so > /etc/ld.so.preload')

    def rhsm_register(self, login, password, pool_id=None):
        # Ensure the RHEL beta channel are disabled
        self.run('rm /etc/pki/product/69.pem', ignore_error=True)
        custom_log = 'subscription-manager register --username %s --password *******' % login
        self.run(
            'subscription-manager register --username %s --password %s' % (
                login, password),
            success_status=(0, 64),
            custom_log=custom_log)
        if pool_id:
            self.run('subscription-manager attach --pool %s' % pool_id)
        else:
            self.run('subscription-manager attach --auto')

    def enable_repositories(self, repositories):
        rhsm_channels = [r['name'] for r in repositories if r['type'] == 'rhsm_channel']
        repo_files = [r for r in repositories if r['type'] == 'yum_repo']

        if rhsm_channels:
            subscription_cmd = "subscription-manager repos '--disable=*' --enable=" + ' --enable='.join(rhsm_channels)
            self.run(subscription_cmd)

        for repo_files in repo_files:
            self.create_file(repo_files['dest'], repo_files['content'])

    def create_stack_user(self):
        self.run('adduser -m stack', success_status=(0, 9))
        self.create_file('/etc/sudoers.d/stack', 'stack ALL=(root) NOPASSWD:ALL\n')
        self.run('mkdir -p /home/stack/.ssh')
        self.run('cp /root/.ssh/authorized_keys /home/stack/.ssh/authorized_keys')
        self.run('chown -R stack:stack /home/stack/.ssh')
        self.run('chmod 700 /home/stack/.ssh')
        self.run('chmod 600 /home/stack/.ssh/authorized_keys')
        self._ssh_pool.build_ssh_client(self.hostname, 'stack',
                                        self._key_filename,
                                        self._via_ip)

    def fetch_image(self, path, checksum, dest, user=None):
        self.create_file("%s.md5" % dest, '%s %s\n' % (checksum, dest))
        if self.run('md5sum -c %s.md5' % dest, user=user, ignore_error=True)[1] != 0:
            self.run('curl -o %s %s' % (dest, path), user=user)

    def install_base_packages(self):
        # TODO(Gonéri): We should install chrony or ntpd
        self.run('yum install -y yum-utils iptables libselinux-python psmisc redhat-lsb-core rsync')

    def clean_system(self):
        self.run('systemctl disable NetworkManager', success_status=(0, 1))
        self.run('systemctl stop NetworkManager', success_status=(0, 5))
        self.run('pkill -9 dhclient', success_status=(0, 1))
        self.run('yum remove -y cloud-init NetworkManager')
        self.run('systemctl enable network')
        self.run('systemctl restart network')

    def update_packages(self, allow_reboot=False):
        self.run('yum update -y')
        # reboot if a new initrd has been generated since the boot
        if allow_reboot:
            self.run('find /boot/ -anewer /proc/1/stat -name "initramfs*" -exec reboot \;')

    def install_osp(self):
        self.run('yum install -y yum-plugin-priorities python-tripleoclient python-rdomanager-oscplugin')

    def set_selinux(self, state):
        allowed_states = ('enforcing', 'permissive', 'disabled')
        if state not in allowed_states:
            raise Exception
        self.run('setenforce %s' % state)
        self.create_file('/etc/sysconfig/selinux',
                         'SELINUX=%s\nSELINUXTYPE=targeted\n' % state)

    def add_environment_file(self, user, filename):
        return self._ssh_pool.add_environment_file(user, filename)
