
import logging

import tripleowrapper.utils as utils

LOG = logging.getLogger('__chainsaw__')


class Server(object):
    def __init__(self, ip, via_ip=None, via_user='root', key_filename=None):
        self.ip = ip
        self.via_ip = via_ip
        self._rhsm_status = None
        self.key_filename = key_filename
        self.ssh_session = {}
        self._run_with_stackrc = False

        self.enable_root_user()

    def enable_root_user(self):
        """Enable the root account on the cloud-image."""
        cloud_user = None
        with utils.SSHSession(self.ip, user='root', via_ip=self.via_ip, key_filename=self.key_filename) as ssh:
            result = ssh.run('uname -a')[0]
            if 'Please login as the user "cloud-user"' in result:
                cloud_user = 'cloud-user'
            else:
                return

        LOG.info('Enabling the root account.')
        print(cloud_user)
        with utils.SSHSession(self.ip, user=cloud_user, via_ip=self.via_ip, key_filename=self.key_filename) as ssh:
            ssh.run("sudo sed -i 's,.*ssh-rsa,ssh-rsa,' /root/.ssh/authorized_keys")

    def get_ssh_session(self, user):
        if user not in self.ssh_session:
            self.ssh_session[user] = utils.SSHSession(
                self.ip, user, via_ip=self.via_ip, key_filename=self.key_filename)
        return self.ssh_session[user]

    def run(self, cmd, user='root', stackrc=False):
        if stackrc:
            cmd = 'source stackrc; ' + cmd
        ssh_session = self.get_ssh_session(user)
        return ssh_session.run(cmd)

    def put_content(self, content, dest, user='root'):
        ssh_session = self.get_ssh_session(user)
        return ssh_session.put_content(content, dest)

    def set_rhsn_credentials(self, login, password, pool_id=None):
        self.rhsm_login = login
        self.rhsm_password = password
        self.rhsm_pool_id = pool_id

    def enable_nosync(self):
        r = self.run('yum install -y https://kojipkgs.fedoraproject.org/packages/nosync/1.0/1.el7/x86_64/nosync-1.0-1.el7.x86_64.rpm')
        if r[1] == 0:
            print(self.run('echo /usr/lib64/nosync/nosync.so > /etc/ld.so.preload'))
        else:
            print('Failed to fetch nosync rpm: %s' % r[0])

    def rhsm_register(self):
        # Ensure the RHEL beta channel are disabled
        self.run('rm /etc/pki/product/69.pem')
        self.run(
            'subscription-manager register --username %s --password %s' % (
                self.rhsm_login,
                self.rhsm_password))
        # TODO(Gonéri): use the correct pool
        if self.rhsm_pool_id:
            self.run('subscription-manager attach --pool ' + self.rhsm_pool_id)
        else:
            self.run('subscription-manager attach --auto')
        self._rhsm_status = 'registered'

    def enable_repositories(self, repositories):
        rhsm_channels = [r['name'] for r in repositories if r['type'] == 'rhsm_channel']
        repo_files = [r for r in repositories if r['type'] == 'yum_repo']

        if rhsm_channels:
            self.rhsm_register()
            subscription_cmd = "subscription-manager repos '--disable=*'" + ' --enable='.join(rhsm_channels)
            self.run(subscription_cmd)

        for repo_files in repo_files:
            self.put_content(repo_files['content'], repo_files['dest'])

    def create_stack_user(self):
        self.run('adduser -m stack')
        self.put_content('stack ALL=(root) NOPASSWD:ALL\n', '/etc/sudoers.d/stack')
        self.run('mkdir -p /home/stack/.ssh')
        self.run('cp /root/.ssh/authorized_keys /home/stack/.ssh/authorized_keys')
        self.run('chown -R stack:stack /home/stack/.ssh')
        self.run('chmod 700 /home/stack/.ssh')
        self.run('chmod 600 /home/stack/.ssh/authorized_keys')

    def fetch_image(self, path, checksum, dest, user='root'):
        self.put_content('%s %s\n' % (checksum, dest), dest + '.md5', user)
        if self.run('md5sum -c %s.md5' % dest)[1] != 0:
            self.run('curl -o %s %s' % (dest, path))

    def install_base_packages(self):
        # TODO(Gonéri): We should install chrony or ntpd
        self.run('yum install -y yum-utils iptables libselinux-python psmisc redhat-lsb-core rsync')

    def clean_system(self):
        self.run('systemctl disable NetworkManager')
        self.run('systemctl stop NetworkManager')
        self.run('pkill -9 dhclient')
        self.run('yum remove -y cloud-init NetworkManager')

    def update_packages(self, allow_reboot=False):
        self.run('yum update -y')
        # reboot if a new initrd has been generated since the boot
        if allow_reboot:
            self.run('find /boot/ -anewer /proc/1/stat -name "initramfs*" -exec reboot \;')
            self.ssh_session['root'] = utils.SSHSession(
                self.ip, user='root', via_ip=self.via_ip, key_filename=self.key_filename)

    def install_osp(self):
        self.run('yum install -y yum-plugin-priorities python-tripleoclient python-rdomanager-oscplugin')

    def set_selinux(self, state):
        allowed_states = ('enforcing', 'permissive', 'disabled')
        if state not in allowed_states:
            raise Exception
        content = 'SELINUX={state}\nSELINUXTYPE=targeted\n'
        self.run('setenforce ' + state)
        self.put_content(content, '/etc/sysconfig/selinux')
