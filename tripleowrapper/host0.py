from tripleowrapper.server import Server
from tripleowrapper.undercloud import Undercloud

from jinja2 import Environment
from jinja2 import FileSystemLoader


class Host0(Server):
    def __init__(self, ip, **kargs):
        Server.__init__(self, ip, **kargs)

    def instack_virt_setup(self):
        self.run('yum install -y libvirt-daemon-driver-nwfilter libvirt-client libvirt-daemon-config-network libvirt-daemon-driver-nodedev libvirt-daemon-kvm libvirt-python libvirt-daemon-config-nwfilter libvirt-glib libvirt-daemon libvirt-daemon-driver-storage libvirt libvirt-daemon-driver-network libvirt-devel libvirt-gobject libvirt-daemon-driver-secret libvirt-daemon-driver-qemu libvirt-daemon-driver-interface libguestfs-tools.noarch virt-install genisoimage openstack-tripleo libguestfs-tools instack-undercloud')
        self.run('sed -i "s,#auth_unix_rw,auth_unix_rw," /etc/libvirt/libvirtd.conf')
        self.run('systemctl start libvirtd')
        self.run('systemctl status libvirtd')
        self.run('mkdir -p /home/stack/DIB')
        self.run('find /etc/yum.repos.d/ -type f -exec cp -v {} /home/stack/DIB \;')

        self.install_base_packages()
        self.clean_system()
        self.update_packages()

        env = Environment()
        env.loader = FileSystemLoader('templates')
        template = env.get_template('virt-setup-env.j2')
        virt_setup_env = template.render(
            {
                'dib_dir': '/home/stack/DIB',
                'node': {
                    'count': 3,
                    'mem': 4096,
                    'cpu': 2
                },
                'undercloud_node_mem': 4096,
                'guest_image_name': '/home/stack/guest_image.qcow2',
                'rhsm': {
                    'user': self.rhsm_login,
                    'password': self.rhsm_password
                }})
        self.put_content(virt_setup_env, 'virt-setup-env', user='stack')
        self.run('source virt-setup-env; instack-virt-setup', user='stack')
        instack_ip = self.run(
            '/sbin/ip n | grep $(tripleo get-vm-mac instack) | awk \'{print $1;}\'', user='stack')[0]
        undercloud = Undercloud(instack_ip, via_ip=self.ip, key_filename=self.key_filename)
        undercloud.run('cp /root/.ssh/authorized_keys /home/stack/.ssh/authorized_keys')
        undercloud.run('chown stack:stack /home/stack/.ssh/authorized_keys')
        undercloud.run('chmod 600 /home/stack/.ssh/authorized_keys')
        return undercloud
