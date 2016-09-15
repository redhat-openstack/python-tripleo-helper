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
import os

from tripleohelper import ssh

LOG = logging.getLogger('tripleohelper')


class Server(object):
    """The base class for all the server objects.

    This class comes with standard function to run command, copy files,
    install packages, activate YUM repositories...

    It also provides some generic methodes specific to OpenStack, like the stack
    user creation.
    """
    def __init__(self, hostname, user='root', via_ip=None, key_filename=None,
                 redirect_to_host=None):
        """:param hostname: IP of the host
        :param user: optional parameter that can be used to explicitly specify the
        admin user.
        :param via_ip: IP of a SSH bastillon to use to connect this host.
        :param key)filename: the local path to the private key of the local user.
        """
        self.hostname = hostname
        self._key_filename = key_filename
        self.via_ip = via_ip
        self.ssh_pool = ssh.PoolSshClient()
        self._redirect_to_host = redirect_to_host
        self.rhsm_active = False
        self.rhsm_channels = [
            'rhel-7-server-rpms',
            'rhel-7-server-optional-rpms',
            'rhel-7-server-extras-rpms']
        self.nosync_rpm = 'https://kojipkgs.fedoraproject.org/packages/nosync/1.0/1.el7/x86_64/nosync-1.0-1.el7.x86_64.rpm'

    def enable_user(self, user):
        """Enable the root account on the remote host.


        Since the host may have been deployed using a Cloud image, it may not
        be possible to use the 'root' account. This method ensure the root
        account is enable, if this is not the case, it will try to get the name
        of admin user and use it to re-enable the root account.
        """
        if user in self.ssh_pool._ssh_clients:
            return

        if user == 'root':
            _root_ssh_client = ssh.SshClient(
                hostname=self.hostname,
                user='root',
                key_filename=self._key_filename,
                via_ip=self.via_ip)

            # connect as a root user
            _root_ssh_client.start()
            result, _ = _root_ssh_client.run('uname -a')

            image_user = None
            # check if root is not allowed
            if 'Please login as the user "cloud-user"' in result:
                image_user = 'cloud-user'
                _root_ssh_client.stop()
            elif 'Please login as the user "fedora" rather than the user "root"' in result:
                image_user = 'fedora'
                _root_ssh_client.stop()

            if image_user:
                self.enable_user(image_user)
                LOG.info('enabling the root user')
                _cmd = "sudo sed -i 's,.*ssh-rsa,ssh-rsa,' /root/.ssh/authorized_keys"
                self.ssh_pool.run(image_user, _cmd)
                _root_ssh_client.start()
            self.ssh_pool.add_ssh_client('root', _root_ssh_client)
            return

        # add the cloud user to the ssh pool
        self.ssh_pool.build_ssh_client(
            hostname=self.hostname,
            user=user,
            key_filename=self._key_filename,
            via_ip=self.via_ip)

    def send_file(self, local_path, remote_path, user='root', unix_mode=None):
        """Upload a local file on the remote host.
        """
        self.enable_user(user)
        return self.ssh_pool.send_file(user, local_path, remote_path, unix_mode=unix_mode)

    def open(self, filename, mode='r', user='root'):
        self.enable_user(user)
        return self.ssh_pool.open(user, filename, mode)

    def create_file(self, path, content, mode='w', user='root'):
        """Create a file on the remote host.
        """
        self.enable_user(user)
        return self.ssh_pool.create_file(user, path, content, mode)

    def run(self, cmd, user='root', sudo=False, ignore_error=False,
            success_status=(0,), error_callback=None, custom_log=None, retry=0):
        """Run a command on the remote host.
        """
        self.enable_user(user)
        return self.ssh_pool.run(
            user, cmd, sudo=sudo, ignore_error=ignore_error,
            success_status=success_status, error_callback=error_callback,
            custom_log=custom_log, retry=retry)

    def get_file_content(self, filename, user='root'):
        with self.open(filename, user=user) as f:
            return f.read().decode()

    def yum_install(self, packages, ignore_error=False):
        """Install some packages on the remote host.

        :param packages: ist of packages to install.
        """
        return self.run('yum install -y --quiet ' + ' '.join(packages), ignore_error=ignore_error, retry=5)

    def yum_remove(self, packages):
        """Remove some packages from a remote host.


        :param packages: ist of packages to remove.
        """
        return self.run('yum remove -y --quiet ' + ' '.join(packages))

    def install_nosync(self):
        """Install and unable lib nosync.

        Install the nosync library to reduce the number of fsync() call and
        speed up the installation.
        """
        _, rc = self.yum_install(
            [self.nosync_rpm],
            ignore_error=True)
        if rc == 0:
            self.run('echo /usr/lib64/nosync/nosync.so > /etc/ld.so.preload')
        else:
            LOG.debug('nosync installation has failed.')

    def rhsm_register(self, rhsm):
        """Register the host on the RHSM.

        :param rhsm: a dict of parameters (login, password, pool_id)
        """
        # Get rhsm credentials
        login = rhsm.get('login')
        password = rhsm.get('password', os.environ.get('RHN_PW'))
        pool_id = rhsm.get('pool_id')
        # Ensure the RHEL beta channel are disabled
        self.run('rm /etc/pki/product/69.pem', ignore_error=True)
        custom_log = 'subscription-manager register --username %s --password *******' % login
        self.run(
            'subscription-manager register --username %s --password "%s"' % (
                login, password),
            success_status=(0, 64),
            custom_log=custom_log,
            retry=3)
        if pool_id:
            self.run('subscription-manager attach --pool %s' % pool_id)
        else:
            self.run('subscription-manager attach --auto')
        self.rhsm_active = True

    def enable_repositories(self, repositories):
        """Enable a list of RHSM repositories.

        :param repositories: a dict in this format:
            [{'type': 'rhsm_channel', 'name': 'rhel-7-server-rpms'}]
        """
        for r in repositories:
            if r['type'] != 'rhsm_channel':
                continue
            if r['name'] not in self.rhsm_channels:
                self.rhsm_channels.append(r['name'])

        if self.rhsm_active:
            subscription_cmd = "subscription-manager repos '--disable=*' --enable=" + ' --enable='.join(
                self.rhsm_channels)
            self.run(subscription_cmd)

        repo_files = [r for r in repositories if r['type'] == 'yum_repo']
        for repo_file in repo_files:
            self.create_file(repo_file['dest'], repo_file['content'])

        packages = [r['name'] for r in repositories if r['type'] == 'package']
        if packages:
            self.yum_install(packages)

    def create_stack_user(self):
        """Create the stack user on the machine.
        """
        self.run('adduser -m stack', success_status=(0, 9))
        self.create_file('/etc/sudoers.d/stack', 'stack ALL=(root) NOPASSWD:ALL\n')
        self.run('mkdir -p /home/stack/.ssh')
        self.run('cp /root/.ssh/authorized_keys /home/stack/.ssh/authorized_keys')
        self.run('chown -R stack:stack /home/stack/.ssh')
        self.run('chmod 700 /home/stack/.ssh')
        self.run('chmod 600 /home/stack/.ssh/authorized_keys')
        self.ssh_pool.build_ssh_client(self.hostname, 'stack',
                                       self._key_filename,
                                       self.via_ip)

    def fetch_image(self, path, dest, checksum=None, user='root'):
        """Store in the user home directory an image from a remote location.
        """
        if checksum:
            self.create_file("%s.md5" % dest, '%s %s\n' % (checksum, dest))
            if self.run('md5sum -c %s.md5' % dest, user=user, ignore_error=True)[1] == 0:
                return
        self.run('curl -s -o %s %s' % (dest, path), user=user)

    def install_base_packages(self):
        """Install some extra packages.
        """
        # TODO(Gonéri): We should install chrony or ntpd
        self.yum_install([
            'yum-utils', 'iptables', 'libselinux-python', 'psmisc',
            'redhat-lsb-core', 'rsync', 'libguestfs-tools'])

    def clean_system(self):
        """Clean up unnecessary packages from the system.
        """
        self.run('systemctl disable NetworkManager', success_status=(0, 1))
        self.run('systemctl stop NetworkManager', success_status=(0, 5))
        self.run('pkill -9 dhclient', success_status=(0, 1))
        self.yum_remove(['cloud-init', 'NetworkManager'])
        self.run('systemctl enable network')
        self.run('systemctl restart network')

    def yum_update(self, allow_reboot=False):
        """Do a yum update on the system.

        :param allow_reboot: If True and if a new kernel has been installed,
        the system will be rebooted
        """
        self.run('yum update -y --quiet', retry=3)
        # reboot if a new initrd has been generated since the boot
        if allow_reboot:
            self.run('find /boot/ -anewer /proc/1/stat -name "initramfs*" -exec reboot \;', ignore_error=True)
            self.ssh_pool.stop_all()

    def install_osp(self):
        """Install the OSP distribution.
        """
        self.yum_install(['yum-plugin-priorities', 'python-tripleoclient', 'python-rdomanager-oscplugin'])

    def set_selinux(self, state):
        """Help to enable/disable SELinux on the host.
        """
        allowed_states = ('enforcing', 'permissive', 'disabled')
        if state not in allowed_states:
            raise Exception
        self.run('setenforce %s' % state)
        self.create_file('/etc/sysconfig/selinux',
                         'SELINUX=%s\nSELINUXTYPE=targeted\n' % state)

    def add_environment_file(self, user, filename):
        """Load an environment file.

        The file will be re-sourced before any new command invocation.
        """
        return self.ssh_pool.add_environment_file(user, filename)
