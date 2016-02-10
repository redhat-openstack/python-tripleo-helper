import copy

import rdomhelper.ssh

import pytest


class FakeSshClient(rdomhelper.ssh.SshClient):
    expectation = []

    def __init__(self, hostname, user, key_filename, via_ip):
        class Client(object):
            def close(self):
                pass
        self.hostname = hostname
        self._environment_filenames = []
        self._client = Client()
        self.description = 'not started yet'

    def load_private_key(self, f):
        pass

    def start(self):
        pass

    def run(self, cmd, **kwargs):
        kwargs['cmd'] = self._prepare_cmd(cmd, sudo=kwargs.get('sudo', False))
        assert FakeSshClient.expectation
        current_expection = FakeSshClient.expectation.pop(0)
        assert current_expection['func'] == 'run'

        # We do not make mandatory to declare in the expectation all the
        # parameters
        ignore_parameters = (
            'sudo',
            'retry',
            'custom_log',
            'success_status',
            'error_callback',
            'ignore_error')
        kwargs_to_compare = {}
        for k, v in kwargs.items():
            if k not in ignore_parameters:
                kwargs_to_compare[k] = v
        assert current_expection['args'] == kwargs_to_compare

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

    def fin():
        msg = 'Some expectations remain unevaluated: %s' % FakeSshClient.expectation
        assert not FakeSshClient.expectation, msg
    request.addfinalizer(fin)
