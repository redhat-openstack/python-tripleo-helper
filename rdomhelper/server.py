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

from rdomhelper import ssh

LOG = logging.getLogger('__chainsaw__')


class Server(object):
    """The base class for all the server objects.

    This class comes with standard function to run command, copy files,
    install packages, activate YUM repositories...

    It also provides some generic methodes specific to RDO-m, like the stack
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
        self._ssh_pool = ssh.PoolSshClient()
        self._redirect_to_host = redirect_to_host
        self._root_user_enabled = False
        self.rhsm_active = False
        self.rhsm_channels = [
            'rhel-7-server-rpms',
            'rhel-7-server-optional-rpms',
            'rhel-7-server-extras-rpms']
        self.nosync_rpm = 'https://kojipkgs.fedoraproject.org/packages/nosync/1.0/1.el7/x86_64/nosync-1.0-1.el7.x86_64.rpm'

    def enable_root_user(self, user):
        """Enable the root account on the remote host.


        Since the host may have been deployed using a Cloud image, it may not
        be possible to use the 'root' account. This method ensure the root
        account is enable, if this is not the case, it will try to get the name
        of admin user and use it to re-enable the root account.
        """
        _root_ssh_client = ssh.SshClient(
            hostname=self.hostname,
            user='root',
            key_filename=self._key_filename,
            via_ip=self.via_ip)

        if user == 'root':
            # connect as a root user
            _root_ssh_client.start()
            result, _ = _root_ssh_client.run('uname -a')

            # check if root is not allowed
            if 'Please login as the user "cloud-user"' in result:
                image_user = 'cloud-user'
                _root_ssh_client.stop()
            elif 'Please login as the user "fedora" rather than the user "root"' in result:
                image_user = 'fedora'
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
            via_ip=self.via_ip)
        # enable the root user
        _cmd = "sudo sed -i 's,.*ssh-rsa,ssh-rsa,' /root/.ssh/authorized_keys"
        self._ssh_pool.run(image_user, _cmd)

        # add the root user to the ssh pool
        _root_ssh_client.start()
        self._ssh_pool.add_ssh_client('root', _root_ssh_client)
        self._root_user_enabled = True

    def send_file(self, local_path, remote_path, user='root', unix_mode=None):
        """Upload a local file on the remote host.
        """
        if not self._root_user_enabled:
            self.enable_root_user(user)
        return self._ssh_pool.send_file(user, local_path, remote_path, unix_mode=unix_mode)

    def create_file(self, path, content, mode='w', user='root'):
        """Create a file on the remote host.
        """
        if not self._root_user_enabled:
            self.enable_root_user(user)
        return self._ssh_pool.create_file(user, path, content, mode)

    def run(self, cmd, user='root', sudo=False, ignore_error=False,
            success_status=(0,), error_callback=None, custom_log=None, retry=0):
        """Run a command on the remote host.
        """
        if not self._root_user_enabled:
            self.enable_root_user(user)
        return self._ssh_pool.run(
            user, cmd, sudo=sudo, ignore_error=ignore_error,
            success_status=success_status, error_callback=error_callback,
            custom_log=custom_log, retry=retry)

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
            'subscription-manager register --username %s --password %s' % (
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
        self._ssh_pool.build_ssh_client(self.hostname, 'stack',
                                        self._key_filename,
                                        self.via_ip)

    def fetch_image(self, path, checksum, dest, user='root'):
        """Store in the user home directory an image from a remote location.
        """
        self.create_file("%s.md5" % dest, '%s %s\n' % (checksum, dest))
        if self.run('md5sum -c %s.md5' % dest, user=user, ignore_error=True)[1] != 0:
            self.run('curl -o %s %s' % (dest, path), user=user)

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
        self.run('yum update -y --quiet')
        # reboot if a new initrd has been generated since the boot
        if allow_reboot:
            self.run('find /boot/ -anewer /proc/1/stat -name "initramfs*" -exec reboot \;')

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
        return self._ssh_pool.add_environment_file(user, filename)

    def _fetch_collectd_rpm(self):
        """Retrieve the rpm needed to install collected on RHEL7.

        We use hardcoded RPM URL because we don't want to enable EPEL repository.
        """
        epel_mirror = 'https://dl.fedoraproject.org/pub/epel/7/x86_64/'
        self.run('cd /tmp; curl -O %s/c/collectd-5.5.1-2.el7.x86_64.rpm' % epel_mirror, user='stack')
        self.run('cd /tmp; curl -O %s/c/collectd-ping-5.5.1-2.el7.x86_64.rpm' % epel_mirror, user='stack')
        self.run('cd /tmp; curl -O %s/l/liboping-1.6.2-2.el7.x86_64.rpm' % epel_mirror, user='stack')
        self.run('yumdownloader --destdir=/tmp libtool-ltdl yajl')

    def inject_collectd(self, image):
        self._fetch_collectd_rpm()
        LOG.info('injecting collectd in %s' % image)
        self.run('cd /tmp; tar cf collectd.tar *.x86_64.rpm', user='stack')
        self.run("""LIBGUESTFS_BACKEND=direct virt-customize -a /home/stack/{image} --upload /tmp/collectd.tar:/tmp/ --run-command 'tar xf /tmp/collectd.tar ; rpm -i --force *.x86_64.rpm' --upload /etc/collectd.conf:/etc/collectd.conf --run-command 'systemctl enable collectd' --run-command 'sed -i "s,After=,After=multi-user.target ," /usr/lib/systemd/system/collectd.service'""".format(image=image))

    def install_collectd(self):
        # Yum is disabled and we want to avoid download over the network
        LOG.info('installing collectd')
        self._fetch_collectd_rpm()
        self.run('cd /tmp ; rpm --force -i *.x86_64.rpm')
        content = """
FQDNLookup  false
BaseDir     "/var/lib/collectd"
PIDFile     "/var/run/collectd.pid"
PluginDir   "/usr/lib64/collectd"
TypesDB     "/usr/share/collectd/types.db"
LoadPlugin  disk
LoadPlugin  interface
LoadPlugin  irq
LoadPlugin  load
LoadPlugin  memory
LoadPlugin  network
LoadPlugin  ping
LoadPlugin  syslog
<Plugin load>
    ReportRelative true
</Plugin>
<Plugin network>
    Server "192.0.2.240" "25826"
</Plugin>
<Plugin ping>
       Host "192.0.2.240"
       Host "8.8.8.8"
</Plugin>
"""
        self.create_file('/etc/collectd.conf', content=content)
        self.run('systemctl start collectd')
