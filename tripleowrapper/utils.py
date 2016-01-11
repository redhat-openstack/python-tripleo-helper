import paramiko

import time


class SSHSession(object):
    def __init__(self, ip, cloud_user='root'):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        for i in range(60):
            try:
                client.connect(ip, port=22, username=cloud_user, allow_agent=True)
            except (OSError, ConnectionResetError):
                print('SSH: Waiting for %s' % ip)
                time.sleep(1)
            else:
                break
        self.client = client

    def __enter__(self):
        return self

    def run(self, cmd):
        transport = self.client.get_transport()
        ch = transport.open_session()
        ch.get_pty()
        ch.set_combine_stderr(True)
        ch.exec_command(cmd)
        buf = ''
        while True:
            new = ch.recv(1024).decode(encoding='UTF-8')
            print(new, end="", flush=True)  # flake8: noqa
            buf += new
            if new == '' and ch.exit_status_ready():
                break
            time.sleep(0.1)
        retcode = ch.recv_exit_status()
        return (buf, retcode)

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
