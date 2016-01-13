import paramiko

import io
import logging
import select
import time

LOG = logging.getLogger('__chainsaw__')


class SSHSession(object):
    def __init__(self, ip, user='root', via_ip=None, key_filename=None):
        self.via_ip = via_ip
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
                break
        self.client = client


    def get_channel(self):
        if self.via_ip:
            channel = self.via_client.get_transport().open_channel(
            'direct-tcpip',
            (self.ip, 22),
            (self.via_ip, 0))
        transport = self.client.get_transport()
        channel = transport.open_session()

        return channel


    def __enter__(self):
        return self

    def run(self, cmd):
        transport = self.client.get_transport()
        ssh_channel = transport.open_session()
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

    def put(self, source, dest):
        transport = self.client.get_transport()
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.put(source, dest)

    def put_content(self, content, dest, mode='w'):
        transport = self.client.get_transport()
        sftp = paramiko.SFTPClient.from_transport(transport)
        file = sftp.file(dest, mode, -1)
        file.write(content)
        file.flush()

    def __exit__(self, exc_type, exc_value, traceback):
        self.client.close()
