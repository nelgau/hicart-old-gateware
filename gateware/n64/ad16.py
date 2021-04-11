from nmigen import *
from nmigen.hdl.rec import DIR_FANIN, DIR_FANOUT
from nmigen.lib.cdc import FFSynchronizer

from test import *

from .burst import BurstBus

class AD16(Record):
    def __init__(self):
        super().__init__([
            ('ad', [
                ('i',    16, DIR_FANIN),
                ('o',    16, DIR_FANOUT),
                ('oe',   1,  DIR_FANOUT),
            ]),         
            ('ale_h',    1,  DIR_FANIN),
            ('ale_l',    1,  DIR_FANIN),
            ('read',     1,  DIR_FANIN),
            ('write',    1,  DIR_FANIN),
            ('s_clk',    1,  DIR_FANIN),
            ('s_data', [
                ('i',    1,  DIR_FANIN),
                ('o',    1,  DIR_FANOUT),
                ('oe',   1,  DIR_FANOUT),
            ]),
            ('cic_dclk', 1, DIR_FANIN),
            ('cic_data', [
                ('i',    1, DIR_FANIN),
                ('o',    1, DIR_FANOUT),
                ('oe',   1, DIR_FANOUT)
            ]),
            ('reset',    1, DIR_FANIN),
            ('nmi',      1, DIR_FANIN),
        ])

class AD16Interface(Elaboratable):
    def __init__(self):
        self.bus = BurstBus()
        self.ad16 = AD16()

    def elaborate(self, platform):
        m = Module()

        ale_h_sync = Signal()
        ale_l_sync = Signal()
        read_sync = Signal()
        ad_i_sync = Signal(16)

        m.submodules += FFSynchronizer( self.ad16.ale_h, ale_h_sync )
        m.submodules += FFSynchronizer( self.ad16.ale_l, ale_l_sync )
        m.submodules += FFSynchronizer( self.ad16.read,  read_sync  )
        m.submodules += FFSynchronizer( self.ad16.ad.i,  ad_i_sync  )

        # Inputs: ad16.ale_l_sync, ad16.ale_h_sync, ad16.ad_i_sync 

        valid = Signal()

        with m.FSM() as fsm:                #   ALE_L       ALE_H
            with m.State("INIT"):           #   Inactive    Inactive
                with m.If(ale_l_sync):
                    m.next = "A"
            
            with m.State("A"):              #   Active      Inactive
                with m.If(~ale_l_sync):
                    m.d.sync += self.bus.base[16:32].eq(ad_i_sync)
                    m.next = "B"

            with m.State("B"):              #   Inactive    Inactive
                with m.If(ale_h_sync):
                    m.next = "C"

            with m.State("C"):              #   Inactive    Active
                with m.If(ale_l_sync):
                    m.d.sync += self.bus.base[1:16].eq(ad_i_sync[1:16])
                    m.next = "VALID"            

            with m.State("VALID"):          #   Active      Active
                with m.If(~ale_h_sync):
                    m.next = "A"

            m.d.comb += valid.eq(fsm.ongoing("VALID"))

        # Inputs: valid, ad16.read_sync, bus.ack
        # Outputs: bus.blk, bus.load, bus.off, bus.cyc, bus.stb, bus.we, ad16.o, ad16.oe

        m.d.sync += [
            self.bus.load.eq(0),
            self.bus.stb.eq(0),
        ]

        with m.FSM() as fsm:
            with m.State("IDLE"):
                with m.If(valid):
                    m.d.sync += self.bus.load.eq(1)
                    m.d.sync += self.bus.off.eq(0)
                    m.next = "BLK"

            with m.State("BLK"):
                with m.If(~valid):
                    m.next = "IDLE"
                with m.Elif(read_sync):
                    m.d.sync += self.bus.stb.eq(1)
                    m.next = "READ"

            with m.State("READ"):
                with m.If(~valid):
                    m.next = "IDLE"
                with m.Elif(self.bus.ack):
                    m.d.sync += self.ad16.ad.o.eq(self.bus.dat_r)
                    m.next = "VALID"

            with m.State("VALID"):
                with m.If(~valid):
                    m.next = "IDLE"
                with m.Elif(~read_sync):
                    m.d.sync += self.bus.off.eq(self.bus.off + 1)
                    m.next = "BLK"

            m.d.comb += self.bus.blk.eq(~fsm.ongoing("IDLE"))
            m.d.comb += self.bus.cyc.eq(fsm.ongoing("READ"))

            m.d.comb += self.ad16.ad.oe.eq(fsm.ongoing("VALID"))

        return m

class AD16InterfaceTest(ModuleTestCase):
    FRAGMENT_UNDER_TEST = AD16Interface

    def traces_of_interest(self):
        return [
            self.dut.bus.blk,
            self.dut.bus.base,
            self.dut.bus.load,
            self.dut.bus.off,
            self.dut.bus.dat_w,
            self.dut.bus.dat_r,
            self.dut.bus.cyc,
            self.dut.bus.stb,
            self.dut.bus.we,
            self.dut.bus.ack,

            self.dut.ad16.ad.i,
            self.dut.ad16.ad.o,
            self.dut.ad16.ad.oe,
            self.dut.ad16.ale_h,
            self.dut.ad16.ale_l,
            self.dut.ad16.read,
            self.dut.ad16.write,
            self.dut.ad16.reset
        ]

    def initialize_signals(self):
        yield self.dut.ad16.ad.i    .eq(0)
        yield self.dut.ad16.ale_h   .eq(0)
        yield self.dut.ad16.ale_l   .eq(0)
        yield self.dut.ad16.read    .eq(0)
        yield self.dut.ad16.write   .eq(0)
        yield self.dut.ad16.reset   .eq(0)

    @sync_test_case
    def test_basic(self):
        # Ale_l is active in idle state
        yield self.dut.ad16.ale_l   .eq(1)
        yield from self.advance_cycles(2)

        # Latch address

        yield self.dut.ad16.ale_l   .eq(0)
        yield self.dut.ad16.ad.i    .eq(0x8765)
        yield
        yield self.dut.ad16.ale_h   .eq(1)
        yield self.dut.ad16.ad.i    .eq(0x4321)
        yield
        yield self.dut.ad16.ale_l   .eq(1)
        yield

        yield from self.advance_cycles(4)

        # 

        self.assertEqual((yield self.dut.bus.blk),  1)
        self.assertEqual((yield self.dut.bus.base), 0x87654320)
        self.assertEqual((yield self.dut.bus.load), 1)

        yield

        self.assertEqual((yield self.dut.bus.load), 0)

        #

        yield from self.advance_cycles(2)

        yield self.dut.ad16.read   .eq(1)
        yield from self.advance_cycles(6)

        #

        yield self.dut.bus.dat_r.eq(0xBABE)
        yield self.dut.bus.ack.eq(1)
        yield

        yield self.dut.bus.ack.eq(0)
        yield        

        self.assertEqual((yield self.dut.ad16.ad.o),  0xBABE)
        self.assertEqual((yield self.dut.ad16.ad.oe), 1)

        #

        yield self.dut.ad16.read   .eq(0)
        yield

        yield from self.advance_cycles(3)

        self.assertEqual((yield self.dut.ad16.ad.oe), 0)

        #

        yield self.dut.ad16.ale_h   .eq(0)
        yield

        yield from self.advance_cycles(4)

        self.assertEqual((yield self.dut.bus.blk),  0)
