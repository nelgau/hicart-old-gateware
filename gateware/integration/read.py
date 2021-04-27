import unittest

from nmigen import *
from nmigen.sim import *
from nmigen_soc import wishbone

from interface.qspi_flash2 import QSPIBus, QSPIFlashWishboneInterface
from n64.ad16 import AD16
from n64.pi import PIWishboneInitiator
from test.driver.ad16 import PIInitiator
from test.emulator.qspi_flash import QSPIFlashEmulator


class DUT(Elaboratable):

    def __init__(self):
        self.ad16 = AD16()
        self.qspi = QSPIBus()

    def elaborate(self, platform):
        m = Module()

        self.initiator = PIWishboneInitiator()
        self.qspi_flash = QSPIFlashWishboneInterface()
        
        self.decoder = wishbone.Decoder(addr_width=32, data_width=32, granularity=8, features={"stall"})
        self.decoder.add(self.qspi_flash.wb, addr=0x10000000)

        m.submodules.initiator  = self.initiator
        m.submodules.qspi_flash = self.qspi_flash
        m.submodules.decoder    = self.decoder

        m.d.comb += [
            self.initiator.ad16     .connect( self.ad16 ),
            self.initiator.bus      .connect( self.decoder.bus ),

            self.qspi_flash.bus     .connect( self.qspi ),
        ]

        return m

    def ports(self):
        return [
            self.ad16.ad.i,
            self.ad16.ad.o,
            self.ad16.ad.oe,
            self.ad16.ale_h,
            self.ad16.ale_l,
            self.ad16.read,
            self.ad16.write,
            self.ad16.reset,

            self.qspi.sck,
            self.qspi.cs_n,
            self.qspi.d.i,
            self.qspi.d.o,
            self.qspi.d.oe,
        ]


class N64ReadTest(unittest.TestCase):

    def test_read(self):
        dut = DUT()

        sim = Simulator(dut)
        pi_driver = PIInitiator(dut.ad16)
        flash_emulator = QSPIFlashEmulator(dut.qspi)

        def driver_process():
            yield from pi_driver.begin()
            yield from pi_driver.read_burst_slow(0x10000000, 2)
            yield from pi_driver.read_burst_fast(0x100048C0, 8)

        def emulator_process():
            yield Passive()
            yield from flash_emulator.emulate()

        sim.add_process(driver_process)
        sim.add_sync_process(emulator_process)
        sim.add_clock(1.0 / 200e6, domain='sync')




        traces = []
        # Add clock signals to the traces by default
        fragment = sim._fragment
        for domain in fragment.iter_domains():
            cd = fragment.domains[domain]
            traces.extend((cd.clk, cd.rst))
        # Add any user-supplied traces after the clock domains
        traces += dut.ports()       


        with sim.write_vcd("test.vcd", "test.gtkw", traces=traces):
            sim.run()        
