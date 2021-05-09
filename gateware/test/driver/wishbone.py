from nmigen.sim import *


class WishboneInitiator:

    def __init__(self, bus):
        self.bus = bus

    def read_once(self, address):
        yield self.bus.cyc.eq(1)
        yield self.bus.stb.eq(1)
        yield self.bus.adr.eq(address)
        yield self.bus.we.eq(0)

        while (yield self.bus.stall):
            yield

        yield

        yield self.bus.stb.eq(0)
        
        while not (yield self.bus.ack):
            yield

        result = (yield self.bus.dat_r)

        yield self.bus.cyc.eq(0)
        yield
