from nmigen import *
from nmigen_soc.wishbone import Interface

from test import *


class DownConverter(Elaboratable):

    def __init__(self, *, sub_bus):        
        self.sub_bus = sub_bus

        self.bus = wishbone.Interface()

    def elaborate(self, platform):
        m = Module()




        return m

class Translator(Elaboratable):

    def __init__(self, *, sub_bus, base_addr=0):        
        self.sub_bus = sub_bus
        self.base_addr = base_addr

        self.bus = Interface(addr_width=sub_bus.addr_width,
                             data_width=sub_bus.data_width,
                             granularity=sub_bus.granularity,
                             features=sub_bus.features) 

        self.bus.memory_map = self.sub_bus.memory_map

    def elaborate(self, platform):
        m = Module()

        m.d.comb += [
            self.bus        .connect(self.sub_bus, exclude={"adr"}),
            self.bus.adr    .eq(self.sub_bus.adr + self.base_addr),
        ]

        return m
