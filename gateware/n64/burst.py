from nmigen import *
from nmigen.hdl.rec import DIR_FANIN, DIR_FANOUT

from nmigen_soc import wishbone

from test import *

class BurstBus(Record):
    def __init__(self):
        super().__init__([
            # Block
            ('blk',         1,  DIR_FANOUT),
            ('base',        32, DIR_FANOUT),
            ('load',        1,  DIR_FANOUT),
            ('blk_stall',   1,  DIR_FANIN),
            # Transfer
            ('off',         8,  DIR_FANOUT),
            ('dat_w',       32, DIR_FANOUT),            
            ('dat_r',       32, DIR_FANIN),
            ('cyc',         1,  DIR_FANOUT),
            ('stb',         1,  DIR_FANOUT),            
            ('we',          1,  DIR_FANOUT),
            ('stall',       1,  DIR_FANIN),            
            ('ack',         1,  DIR_FANIN),
        ])

class _AddressGenerator(Elaboratable):
    def __init__(self):
        self.addr = Signal(32)
        self.base = Signal(32)
        self.offset = Signal(8)

    def elaborate(self, platform):
        m = Module()

        m.d.comb += [
            self.addr[0:8]  .eq((self.base[0:8] + self.offset)[0:8]),
            self.addr[8:32] .eq(self.base[8:32])
        ]

        return m

class BurstDecoder(Elaboratable):
    def __init__(self):
        self.bus = BurstBus()
        self.direct = BurstBus()
        self.buffered = BurstBus()

    def elaborate(self, platform):
        m = Module()

        m.d.comb += self.bus.connect(self.direct)

        return m

class DirectBurst2Wishbone(Elaboratable):
    """ Pass-through burst to Wishbone adapter """

    def __init__(self):
        self.bbus = BurstBus()
        self.wbbus = wishbone.Interface(addr_width=32, data_width=32)

    def elaborate(self, platform):
        m = Module()

        m.submodules.agen = agen = _AddressGenerator()

        m.d.comb += [
            agen.base           .eq(self.bbus.base),
            agen.offset         .eq(self.bbus.off),

            self.wbbus.cyc      .eq(self.bbus.cyc),
            self.wbbus.stb      .eq(self.bbus.stb),
            self.wbbus.we       .eq(self.bbus.we),
            self.bbus.ack       .eq(self.wbbus.ack),

            self.wbbus.adr      .eq(agen.addr),
            self.wbbus.dat_w    .eq(self.bbus.dat_w),
            self.bbus.dat_r     .eq(self.wbbus.dat_r),
        ]

        return m

class BufferedBurst2Wishbone(Elaboratable):
    """ Buffered burst to Wishbone adapter """

    def __init__(self):
        self.bbus = BurstBus()
        self.wbbus = wishbone.Interface(addr_width=32, data_width=32)

    def elaborate(self, platform):
        m = Module()

        # m.submodules.agen = agen = _AddressGenerator()

        m.d.comb += [
            # agen.base           .eq(self.bbus.base),
            # agen.offset         .eq(self.bbus.off),

            self.wbbus.cyc      .eq(0),
            self.wbbus.stb      .eq(0),
            self.wbbus.we       .eq(0),
            self.bbus.ack       .eq(0),

            self.wbbus.adr      .eq(0),
            self.wbbus.dat_w    .eq(0),
            self.bbus.dat_r     .eq(0),
        ]

        return m
