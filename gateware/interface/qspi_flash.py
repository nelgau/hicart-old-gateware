from nmigen import *
from nmigen.hdl.rec import DIR_FANIN, DIR_FANOUT
from nmigen_soc import wishbone

from test import *


class QSPIBus(Record):
    def __init__(self):
        super().__init__([
            ('sck',  1, DIR_FANOUT),
            ('cs_n', 1, DIR_FANOUT),
            ('d', [
                ('i',  4, DIR_FANIN),
                ('o',  4, DIR_FANOUT),
                ('oe', 4, DIR_FANOUT),
            ]),            
        ])


class QSPIFlashInterface(Elaboratable):

    def __init__(self):
        self.bus = QSPIBus()
        self.wb = wishbone.Interface(addr_width=24, data_width=32, features={"stall"})

    def elaborate(self, platform):
        m = Module()

        foo = Signal()
        m.d.sync += foo.eq(1)

        return m


class QSPIFlashInterfaceTest(ModuleTestCase):
    FRAGMENT_UNDER_TEST = QSPIFlashInterface

    def traces_of_interest(self):
        return [
            self.dut.bus.sck,
            self.dut.bus.cs_n,
            
            self.dut.bus.d.i,
            self.dut.bus.d.o,
            self.dut.bus.d.oe,

            self.dut.wb.cyc,
            self.dut.wb.stb,
            self.dut.wb.we,
            self.dut.wb.stall,
            self.dut.wb.ack,

            self.dut.wb.adr,
            self.dut.wb.dat_r,
            self.dut.wb.dat_w,
        ]    

    @sync_test_case
    def test_basic(self):
        yield from self.advance_cycles(10)
