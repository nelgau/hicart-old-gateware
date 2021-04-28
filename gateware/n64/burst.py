from nmigen import *
from nmigen.sim import *
from nmigen.hdl.rec import DIR_FANIN, DIR_FANOUT

from nmigen_soc import wishbone

from test import MultiProcessTestCase

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
        self.wbbus = wishbone.Interface(addr_width=32, data_width=32, features={"stall"})

    def elaborate(self, platform):
        m = Module()

        m.submodules.agen = agen = _AddressGenerator()

        base = Signal(32)
        offset = Signal(8)

        with m.FSM() as fsm:

            m.d.comb += [
                self.bbus.blk_stall             .eq(~fsm.ongoing("IDLE")),
            ]

            with m.State("IDLE"):

                with m.If(self.bbus.blk & self.bbus.load):
                    m.next = "OP_BEGIN"
                    m.d.sync += [
                        base                    .eq(self.bbus.base),
                        offset                  .eq(self.bbus.off),
                    ]

            with m.State("OP_BEGIN"):
                m.d.comb += self.wbbus.cyc      .eq(1)
                m.d.comb += self.wbbus.stb      .eq(1)

                with m.If(~self.wbbus.stall):
                    m.next = "OP_WAIT"

            with m.State("OP_WAIT"):
                m.d.comb += self.wbbus.cyc      .eq(1)

                with m.If(self.wbbus.ack):

                    with m.If(self.bbus.blk & (offset != 127)):
                        m.next = "OP_BEGIN"
                        m.d.sync += offset      .eq(offset + 1)
                    with m.Else():
                        m.next = "IDLE"


                    # m.d.comb += [
                    #     op_read_data            .eq(self.bus.dat_r),
                    #     op_read_data_valid      .eq(1),
                    # ]            



        m.d.comb += [
            agen.base           .eq(base),
            agen.offset         .eq(offset),
            self.wbbus.adr      .eq(agen.addr),

            # self.bbus.ack       .eq(0),

            # self.bbus.dat_r     .eq(0),
        ]

        return m

    def ports(self):
        return [
            self.bbus,
            self.wbbus,
        ]

class BufferedBurst2WishboneTest(MultiProcessTestCase):

    def test_basic(self):
        dut = BufferedBurst2Wishbone()

        def bbus_process():
            yield

            yield dut.bbus.blk          .eq(1)
            yield dut.bbus.load         .eq(1)
            yield dut.bbus.base         .eq(0x1000)
            yield

            yield dut.bbus.load         .eq(0)
            yield

            for i in range(20):
                yield

            yield dut.bbus.blk          .eq(0)

            for i in range(20):
                yield            

        def wbbus_process():
            yield Passive()

            while True:
                while (yield ~(dut.wbbus.cyc & dut.wbbus.stb)):
                    yield

                yield
                yield dut.wbbus.stall       .eq(1)

                yield
                yield
                yield dut.wbbus.ack         .eq(1)
                yield
                yield dut.wbbus.stall       .eq(0)
                yield dut.wbbus.ack         .eq(0)

        with self.simulate(dut, traces=dut.ports()) as sim:
            sim.add_clock(1.0 / 100e6, domain='sync')
            sim.add_sync_process(bbus_process)
            sim.add_sync_process(wbbus_process)
