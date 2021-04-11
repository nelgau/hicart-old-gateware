from nmigen import *

from nmigen_soc import wishbone

from .ad16 import AD16, AD16Interface
from .burst import BurstDecoder, DirectBurst2Wishbone, BufferedBurst2Wishbone

from test import *

from lambdasoc.periph.sram  import SRAMPeripheral

class PIInitiator(Elaboratable):
    def __init__(self):
        self.bus = wishbone.Interface(addr_width=32, data_width=16)
        self.ad16 = AD16()

    def elaborate(self, platform):
        m = Module()

        m.submodules.interface = interface = AD16Interface()
        m.submodules.decoder   = decoder   = BurstDecoder()
        m.submodules.direct    = direct    = DirectBurst2Wishbone()
        m.submodules.buffered  = buffered  = BufferedBurst2Wishbone()
        m.submodules.arbiter   = arbiter   = wishbone.Arbiter(addr_width=32, data_width=16)

        arbiter.add(direct.wbbus)
        arbiter.add(buffered.wbbus)

        m.d.comb += [
            interface.ad16      .connect( self.ad16     ),
            interface.bus       .connect( decoder.bus   ),
            decoder.direct      .connect( direct.bbus   ),
            decoder.buffered    .connect( buffered.bbus ),
            arbiter.bus         .connect( self.bus      )
        ]

        return m

class PIInitiatorTest(ModuleTestCase):

    class DUT(Elaboratable):

        def __init__(self):
            self.ad16 = AD16()

            self.rom_data = [
                0x4001,
                0x4002,
                0x4003,
                0x4004,
            ]

        def elaborate(self, platform):
            m = Module()

            self.decoder = wishbone.Decoder(addr_width=32, data_width=16)

            self.rom = SRAMPeripheral(size=4, data_width=16, writable=False)
            self.decoder.add(self.rom.bus, addr=0x10000000)

            self.initiator = PIInitiator()

            m.submodules.initiator = self.initiator
            m.submodules.decoder   = self.decoder
            m.submodules.rom       = self.rom

            m.d.comb += [
                self.initiator.ad16 .connect( self.ad16 ),
                self.initiator.bus  .connect( self.decoder.bus ),
            ]

            return m

    FRAGMENT_UNDER_TEST = DUT

    def traces_of_interest(self):
        return [
            self.dut.ad16.ad.i,
            self.dut.ad16.ad.o,
            self.dut.ad16.ad.oe,
            self.dut.ad16.ale_h,
            self.dut.ad16.ale_l,
            self.dut.ad16.read,
            self.dut.ad16.write,
            self.dut.ad16.reset
        ]        

    @sync_test_case
    def test_basic(self):
        # Ale_l is active in idle state
        yield self.dut.ad16.ale_l   .eq(1)
        yield from self.advance_cycles(2)

        # Latch address

        yield self.dut.ad16.ale_l   .eq(0)
        yield self.dut.ad16.ad.i    .eq(0x1000)
        yield
        yield self.dut.ad16.ale_h   .eq(1)
        yield self.dut.ad16.ad.i    .eq(0x0002)
        yield
        yield self.dut.ad16.ale_l   .eq(1)
        yield from self.advance_cycles(8)

        #

        yield self.dut.ad16.read   .eq(1)
        yield from self.advance_cycles(6)
        yield self.dut.ad16.read   .eq(0)
        yield from self.advance_cycles(6)

        yield self.dut.ad16.read   .eq(1)
        yield from self.advance_cycles(6)
        yield self.dut.ad16.read   .eq(0)
        yield from self.advance_cycles(6)
