from tripleowrapper.server import Server


class Undercloud(Server):
    def __init__(self, ip):
        Server.__init__(self, ip)
