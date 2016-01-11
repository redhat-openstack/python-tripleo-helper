
import logging

import tripleowrapper.utils as utils

LOG = logging.getLogger('__chainsaw__')


class Server(object):
    def __init__(self, ip):
        self.ip = ip
        self._rhsm_status = None
        self.enable_root_user()

    def enable_root_user(self):
        """Enable the root account on the cloud-image."""
        cloud_user = None
        with utils.SSHSession(self.ip, 'root') as ssh:
            result = ssh.run('uname -a')[0]
            if 'Please login as the user "cloud-user"' in result:
                cloud_user = 'cloud-user'
            else:
                return

        LOG.info('Enabling the root account.')
        with utils.SSHSession(self.ip, cloud_user) as ssh:
            ssh.run("sudo sed -i 's,.*ssh-rsa,ssh-rsa,' /root/.ssh/authorized_keys")

    def set_rhsn_credentials(self, login, password, pool_id=None):
        self.rhsm_login = login
        self.rhsm_password = password
        self.rhsm_pool_id = pool_id

    def enable_nosync(self):
        with utils.SSHSession(self.ip) as ssh:
            if ssh.run('yum install -y https://kojipkgs.fedoraproject.org//packages/nosync/1.0/1.el7/x86_64/nosync-1.0-1.el7.x86_64.rpm')[1] == 0:
                print(ssh.run(' echo /usr/lib64/nosync/nosync.so > /etc/ld.so.preload'))
            else:
                print('Failed to fetch nosync rpm')

    def rhsm_register(self):
        with utils.SSHSession(self.ip) as ssh:
            # Ensure the RHEL beta channel are disabled
            ssh.run('rm /etc/pki/product/69.pem')
            ssh.run(
                'subscription-manager register --username %s --password %s' % (
                    self.rhsm_login,
                    self.rhsm_password))
            # TODO(Gonéri): use the correct pool
            if self.rhsm_pool_id:
                ssh.run('subscription-manager attach --pool ' + self.rhsm_pool_id)
            else:
                ssh.run('subscription-manager attach --auto')
        self._rhsm_status = 'registered'

    def enable_repositories(self, repositories):
        rhsm_channels = [r['name'] for r in repositories if r['type'] == 'rhsm_channel']
        repo_files = [r for r in repositories if r['type'] == 'yum_repo']

        if rhsm_channels:
            self.rhsm_register()
            subscription_cmd = "subscription-manager repos '--disable=*'" + ' --enable='.join(rhsm_channels)
            with utils.SSHSession(self.ip) as ssh:
                ssh.run(subscription_cmd)

        with utils.SSHSession(self.ip) as ssh:
            ssh.run(subscription_cmd)
            for repo_files in repo_files:
                ssh.put_content(repo_files['content'], repo_files['dest'])
