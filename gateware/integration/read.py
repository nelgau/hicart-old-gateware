import unittest

from nmigen import *
from nmigen.sim import *
from nmigen_soc import wishbone

from interface.qspi_flash import QSPIBus, QSPIFlashWishboneInterface
from n64.ad16 import AD16
from n64.pi import PIWishboneInitiator
from test.driver.ad16 import PIInitiator
from test.emulator.qspi_flash import QSPIFlashEmulator

from test import MultiProcessTestCase


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


class N64ReadTest(MultiProcessTestCase):

    def test_read(self):
        dut = DUT()

        data = [
            0xCAFE,
            0xBABE,
            0xDEAD,
            0xBEEF
        ]

        rom_data = self._rom_bytes(data, 2, 'big')
        flash = QSPIFlashEmulator(dut.qspi, rom_data)
        pi = PIInitiator(dut.ad16)

        def flash_process():
            yield Passive()
            yield from flash.emulate()

        def pi_process():
            yield from pi.begin()
            yield from pi.read_burst_slow(0x10000000, 2)
            yield from pi.read_burst_fast(0x10000000, 32)

        with self.simulate(dut, traces=dut.ports()) as sim:
            sim.add_clock(1.0 / 80e6, domain='sync')
            sim.add_sync_process(flash_process)
            sim.add_process(pi_process)

    @staticmethod
    def _rom_bytes(data, data_width, byteorder):
        return [b for w in data for b in w.to_bytes(data_width, byteorder=byteorder)]
