
import logging

import tripleowrapper.utils as utils

LOG = logging.getLogger('__chainsaw__')


class Server(object):
    def __init__(self, ip, via_ip=None, via_user='root'):
        self.ip = ip
        self.via_ip = via_ip
        self._rhsm_status = None
        self.enable_root_user()
        self.ssh_session = {}

    def enable_root_user(self):
        """Enable the root account on the cloud-image."""
        cloud_user = None
        with utils.SSHSession(self.ip, 'root', via_ip=self.via_ip) as ssh:
            result = ssh.run('uname -a')[0]
            if 'Please login as the user "cloud-user"' in result:
                cloud_user = 'cloud-user'
            else:
                return

        LOG.info('Enabling the root account.')
        with utils.SSHSession(self.ip, cloud_user, via_ip=self.via_ip) as ssh:
            self.run("sudo sed -i 's,.*ssh-rsa,ssh-rsa,' /root/.ssh/authorized_keys")

    def get_ssh_session(self, user):
        if user not in self.ssh_session:
            self.ssh_session[user] = utils.SSHSession(self.ip, 'root', via_ip=self.via_ip)
        return self.ssh_session[user]

    def run(self, cmd, user='root'):
        ssh_session = self.get_ssh_session(user)
        return ssh_session.run(cmd)

    def put_content(self, content, dest, user='root'):
        ssh_session = self.get_ssh_session(user)
        return ssh_session.run(content, dest)

    def set_rhsn_credentials(self, login, password, pool_id=None):
        self.rhsm_login = login
        self.rhsm_password = password
        self.rhsm_pool_id = pool_id

    def enable_nosync(self):
        if ssh.run('yum install -y https://kojipkgs.fedoraproject.org/packages/nosync/1.0/1.el7/x86_64/nosync-1.0-1.el7.x86_64.rpm')[1] == 0:
            print(ssh.run(' echo /usr/lib64/nosync/nosync.so > /etc/ld.so.preload'))
        else:
            print('Failed to fetch nosync rpm')

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
