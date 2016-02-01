import copy

import rdomhelper.ssh

import pytest


class FakeSshClient(rdomhelper.ssh.SshClient):
    expectation = []

    def __init__(self, hostname, user, key_filename, via_ip):
        self.hostname = hostname

    def load_private_key(self, f):
        pass

    def start(self):
        pass

    def run(self, cmd, **kwargs):
        kwargs['cmd'] = cmd
        defaults = {
            'sudo': False,
            'custom_log': None,
            'success_status': (0,),
            'error_callback': None,
            'ignore_error': False
        }
        assert FakeSshClient.expectation
        current_expection = FakeSshClient.expectation.pop(0)
        assert current_expection['func'] == 'run'

        for k, v in defaults.items():
            if k not in current_expection:
                if k in kwargs:
                    del kwargs[k]

        assert current_expection['args'] == kwargs

        cmd_output, exit_status = current_expection.get('res', ('', 0))
        return self._evaluate_run_result(
            exit_status,
            cmd_output,
            kwargs.get('ignore_error'),
            kwargs.get('success_status', (0,)),
            kwargs.get('error_callback'))

    def create_file(self, path, content, mode='w'):
        kwargs = {}
        kwargs['path'] = path
        kwargs['content'] = content
        if mode != 'w':
            kwargs['mode'] = mode
        assert FakeSshClient.expectation
        current_expection = FakeSshClient.expectation.pop(0)
        assert current_expection['func'] == 'create_file'
        assert current_expection['args'] == kwargs


@pytest.fixture(scope='function')
def fake_sshclient(monkeypatch, request):
    FakeSshClient.expectation = copy.deepcopy(request.param)
    monkeypatch.setattr('rdomhelper.ssh.SshClient', FakeSshClient)
