from tripleowrapper.server import Server


class Undercloud(Server):
    def __init__(self, ip, **kargs):
        print(kargs)
        Server.__init__(self, ip, **kargs)
