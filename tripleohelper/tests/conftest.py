import copy

import tripleohelper.baremetal
import tripleohelper.ovb_baremetal
import tripleohelper.ovb_undercloud
import tripleohelper.server
import tripleohelper.ssh
import tripleohelper.undercloud

import mock
import pytest


class FakeSshClient(tripleohelper.ssh.SshClient):
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
    monkeypatch.setattr('tripleohelper.ssh.SshClient', FakeSshClient)

    def fin():
        msg = 'Some expectations remain unevaluated: %s' % FakeSshClient.expectation
        assert not FakeSshClient.expectation, msg
    request.addfinalizer(fin)


@pytest.fixture
def server_without_root_enabled(fake_sshclient):
    s = tripleohelper.server.Server(hostname='toto')
    return s


@pytest.fixture
def server(server_without_root_enabled):
    s = tripleohelper.server.Server(hostname='toto')
    s._root_user_enabled = True
    ssh = FakeSshClient(None, None, None, None)
    s.ssh_pool.add_ssh_client('stack', ssh)
    s.ssh_pool.add_ssh_client('root', ssh)
    return s


@pytest.fixture
def undercloud(fake_sshclient):
    s = tripleohelper.undercloud.Undercloud(hostname='toto')
    s._root_user_enabled = True
    ssh = FakeSshClient(None, None, None, None)
    s.ssh_pool.add_ssh_client('stack', ssh)
    s.ssh_pool.add_ssh_client('root', ssh)
    s.baremetal_factory = tripleohelper.baremetal.BaremetalFactory(
        instackenv_content='[{"pm_addr": "neverland", "pm_user": "root", "pm_password": "pw"}]')
    return s


@pytest.fixture
def nova_api():
    test_nova_api = mock.Mock()
    test_nova_api.flavors.list.return_value = []
    floating_ips = [mock.Mock(), mock.Mock()]
    for f in floating_ips:
        f.instance_id = None
        f.fixed_ip = None
    floating_ips[0].ip = '1.2.3.3'
    floating_ips[1].ip = '1.2.3.4'
    test_nova_api.floating_ips.list.return_value = floating_ips
    test_nova_api.images.list.return_value = []
    test_nova_api.keypairs.list.return_value = []
    test_nova_api.networks.list.return_value = []
    server = mock.Mock()
    server.status = 'ACTIVE'
    test_nova_api.servers.create.return_value = server
    return test_nova_api


@pytest.fixture
def neutron():
    test_neutron = mock.Mock()
    test_neutron.create_port.return_value = {'port': {'id': 1}}
    return test_neutron


@pytest.fixture
def ovb_undercloud(fake_sshclient, nova_api, neutron):
    s = tripleohelper.ovb_undercloud.OVBUndercloud()
    s._root_user_enabled = True
    ssh = FakeSshClient(None, None, None, None)
    s.ssh_pool.add_ssh_client('stack', ssh)
    s.ssh_pool.add_ssh_client('root', ssh)
    s.start(
        nova_api=nova_api,
        neutron=neutron,
        provisioner={
            'image': {'name': 'RHEL7'},
            'keypair': 'someone',
            'network': 'skynet',
            'security-groups': ['ssh']})
    s.baremetal_factory = tripleohelper.ovb_baremetal.BaremetalFactory(
        nova_api=nova_api,
        neutron=neutron,
        keypair='someone',
        key_filename='somewhere',
        security_groups=['ssh'])
    return s
