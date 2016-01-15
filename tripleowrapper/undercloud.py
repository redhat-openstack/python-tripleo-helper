from tripleowrapper.server import Server


class Undercloud(Server):
    def __init__(self, ip, **kargs):
        Server.__init__(self, ip, **kargs)

    def deploy(self, guest_image_path, guest_image_checksum, files):
        for name, file in files.items():
            self.fetch_image(
                path=file['path'],
                checksum=file['checksum'],
                dest='/home/stack/%s.tar' % name,
                user='stack')
            self.run('tar xf %s.tar' % name, user='stack')
        self.fetch_image(
            path=guest_image_path,
            checksum=guest_image_checksum,
            dest='/home/stack/guest_image.qcow2',
            user='stack')
        hostname_s = self.run('hostname -s')[0].rstrip('\n')
        hostname_f = self.run('cat /etc/hostname')[0].rstrip('\n')
        self.run("sed 's,127.0.0.1,127.0.0.1 %s %s,' /etc/hosts" % (hostname_s, hostname_f), user='root')
        self.set_selinux('permissive')
        self.run('openstack undercloud install', user='stack')
        self.run('heat stack list', user='stack', stackrc=True)
        self.run('openstack overcloud image upload', user='stack', stackrc=True)
        self.run('openstack baremetal import --json instackenv.json', user='stack', stackrc=True)
        self.run('openstack baremetal configure boot', user='stack', stackrc=True)
        self.run('openstack flavor create --id auto --ram 4096 --disk 40 --vcpus 1 baremetal', user='stack', stackrc=True)

    def start_overcloud(self):
        self.run('openstack flavor set --property "cpu_arch"="x86_64" --property "capabilities:boot_option"="local" baremetal', user='stack', stackrc=True)
        self.run('openstack overcloud deploy --templates -e /usr/share/openstack-tripleo-heat-templates/overcloud-resource-registry-puppet.yaml', user='stack', stackrc=True)
