from tripleowrapper.server import Server


class Undercloud(Server):
    def __init__(self, ip, **kargs):
        print(kargs)
        Server.__init__(self, ip, **kargs)

    def deploy(self, overcloud):
        for name, file in overcloud['files'].items():
            self.fetch_image(
                path=file['path'],
                checksum=file['checksum'],
                dest='/home/stack/%s.tar' % name,
                user='stack')
            self.run('tar xf %s.tar' % name, user='stack')
        self.fetch_image(
            path=overcloud['guest_image_path'],
            checksum=overcloud['guest_image_checksum'],
            dest='/home/stack/guest_image.qcow2',
            user='stack')
        self.run('openstack undercloud install', user='stack')
