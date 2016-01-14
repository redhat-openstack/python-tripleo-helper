import paramiko

import io
import logging
import select
import time

LOG = logging.getLogger('__chainsaw__')


class SSHSession(object):
    def __init__(self, ip, user='root', via_ip=None, key_filename=None):
        self.ip = ip
        self.user = user
        self.via_ip = via_ip

        self.load_private_key(key_filename)

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print('via_ip %s' % via_ip)
        print('ip %s' % ip)
        connect_to = via_ip if via_ip else ip
        for i in range(60):
            try:
                client.connect(
                    connect_to,
                    username=user,
                    allow_agent=True,
                    key_filename=None)
            except (OSError, ConnectionResetError):
                print('SSH: Waiting for %s' % ip)
                time.sleep(1)
            else:
                self.client = client
        self.transport = self.get_transport()


    def load_private_key(self, priv_key):
        """Register the SSH private key."""
        with open(priv_key) as fd:
            self.private_key = paramiko.RSAKey.from_private_key(fd)

    def get_transport(self):
        if self.via_ip:
            channel = self.client.get_transport().open_channel(
            'direct-tcpip',
            (self.ip, 22),
            (self.via_ip, 0))
            transport = paramiko.Transport(channel)
            transport.start_client()
            transport.auth_publickey(self.user, self.private_key)
        else:
            transport = self.client.get_transport()
        transport.set_keepalive(10)
        return transport


    def __enter__(self):
        return self

    def run(self, cmd):
        ssh_channel = self.transport.open_session()
        cmd_output = io.StringIO()
        ssh_channel.set_combine_stderr(True)
        ssh_channel.get_pty()

        LOG.info("(%s)run '%s'" % (self.user, cmd))
        ssh_channel.exec_command(cmd)

        while True:
            if ssh_channel.exit_status_ready():
                break
            rl, _, _ = select.select([ssh_channel], [], [], 30)
            if rl:
                received = ssh_channel.recv(1024).decode('UTF-8', 'ignore')
                LOG.debug(received)
                cmd_output.write(received)
        return cmd_output.getvalue(), ssh_channel.exit_status

    def put(self, source, dest):
        sftp = paramiko.SFTPClient.from_transport(selftransport)
        sftp.put(source, dest)

    def put_content(self, content, dest, mode='w'):
        sftp = paramiko.SFTPClient.from_transport(self.transport)
        file = sftp.file(dest, mode, -1)
        file.write(content)
        file.flush()

    def __exit__(self, exc_type, exc_value, traceback):
        self.transport.close()
        self.client.close()
