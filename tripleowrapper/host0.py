from tripleowrapper.server import Server
import tripleowrapper.utils as utils

from jinja2 import Environment
from jinja2 import FileSystemLoader


class Host0(Server):
    def __init__(self, ip, **kargs):
        Server.__init__(self, ip, **kargs)

    def instack_virt_setup(self, guest_image_path, guest_image_md5sum):
        with utils.SSHSession(self.ip) as ssh:
            ssh.run('adduser -m stack')
            ssh.put_content('stack ALL=(root) NOPASSWD:ALL\n', '/etc/sudoers.d/stack')
            ssh.run('mkdir -p /home/stack/.ssh')
            ssh.run('cp /root/.ssh/authorized_keys /home/stack/.ssh/authorized_keys')
            ssh.run('chown -R stack:stack /home/stack/.ssh')
            ssh.run('chmod 700 /home/stack/.ssh')
            ssh.run('chmod 600 /home/stack/.ssh/authorized_keys')
            ssh.run('yum install -y libvirt-daemon-driver-nwfilter libvirt-client libvirt-daemon-config-network libvirt-daemon-driver-nodedev libvirt-daemon-kvm libvirt-python libvirt-daemon-config-nwfilter libvirt-daemon-driver-lxc libvirt-glib libvirt-daemon libvirt-daemon-driver-storage libvirt libvirt-daemon-driver-network libvirt-devel libvirt-gobject libvirt-daemon-driver-secret libvirt-daemon-driver-qemu libvirt-daemon-driver-interface libvirt-docs libguestfs-tools.noarch virt-install genisoimage openstack-tripleo libguestfs-tools')
            ssh.run('sed -i "s,#auth_unix_rw,auth_unix_rw," /etc/libvirt/libvirtd.conf')
            ssh.run('systemctl start libvirtd')
            ssh.run('systemctl status libvirtd')
            ssh.run('mkdir -p /home/stack/DIB')
            ssh.run('find /etc/yum.repos.d/ -type f -exec cp -v {} /home/stack/DIB \;')
        # TODO(Gonéri): We should install chrony or ntpd
            ssh.run('yum install -y yum-utils iptables libselinux-python psmisc redhat-lsb-core rsync')
            ssh.run('systemctl disable NetworkManager')
            ssh.run('systemctl stop NetworkManager')
            ssh.run('pkill -9 dhclient')
            ssh.run('yum remove -y cloud-init NetworkManager')
            ssh.run('yum update -y')
        # reboot if a new initrd has been generated since the boot
            ssh.run('yum install -y yum-plugin-priorities python-tripleoclient python-rdomanager-oscplugin')
            ssh.run('find /boot/ -anewer /proc/1/stat -name "initramfs*" -exec reboot \;')
        with utils.SSHSession(self.ip, 'stack') as ssh:
            ssh.put_content('%s guest_image.qcow2\n' % guest_image_md5sum, 'guest_image.qcow2.md5')
            if ssh.run('md5sum -c /home/stack/guest_image.qcow2.md5')[1] != 0:
                print(ssh.run('curl -o /home/stack/guest_image.qcow2 %s' % guest_image_path))
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
            ssh.put_content(virt_setup_env, 'virt-setup-env')
            ssh.run('source virt-setup-env; instack-virt-setup')
            instack_ip = ssh.run('/sbin/ip n | grep $(tripleo get-vm-mac instack) | awk \'{print $1;}\'')[0]
            undercloud = Undercloud(instack_ip, via_ip=self.ip)
            with utils.SSHSession(undercloud.ip, via_ip=undercloud.via_ip) as undercloud_ssh:
                ssh.run('')
                return undercloud
