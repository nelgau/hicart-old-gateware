import unittest

from nmigen import *
from nmigen.hdl.ast import Rose, Fell
from nmigen.hdl.rec import DIR_FANIN, DIR_FANOUT
from nmigen.lib.cdc import FFSynchronizer, AsyncFFSynchronizer

from nmigen_soc import wishbone

from test import *

class N64CartBus(Record):
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

class N64Initiator(Elaboratable):
    def __init__(self):
        self.bus = wishbone.Interface(addr_width=32, data_width=16, granularity=8)
        self.cart = N64CartBus()

        self.addr = Signal(32)
        self.valid = Signal()

    def elaborate(self, platform):
        m = Module()

        ale_h_sync = Signal()
        ale_l_sync = Signal()
        read_sync = Signal()
        ad_i_sync = Signal(16)

        m.submodules += FFSynchronizer( self.cart.ale_h, ale_h_sync )
        m.submodules += FFSynchronizer( self.cart.ale_l, ale_l_sync )
        m.submodules += FFSynchronizer( self.cart.read,  read_sync  )
        m.submodules += FFSynchronizer( self.cart.ad.i,  ad_i_sync  )

        addr_l_valid = Signal()
        addr_h_valid = Signal()
        begin_read   = Signal()

        result_data  = Signal(16)
        result_valid = Signal(0)

        with m.If(Fell(ale_l_sync, domain='sync')):
            m.d.sync += self.cart.ad.oe.eq(0)

        with m.If(Rose(ale_h_sync, domain='sync')):
            m.d.sync += [
                self.addr[16:32]        .eq(ad_i_sync),
                addr_h_valid            .eq(1),
                addr_l_valid            .eq(0)            
            ]

        with m.If(Rose(ale_l_sync, domain='sync')):
            m.d.sync += [
                self.addr[1:16]         .eq(ad_i_sync[1:16]),
                self.addr[0]            .eq(0),
                addr_l_valid            .eq(1),
                begin_read              .eq(1)
            ]

        m.d.comb += self.valid.eq(addr_l_valid & addr_h_valid)

        with m.If(Rose(read_sync, domain='sync')):
            with m.If(self.valid):
                m.d.sync += [
                    self.addr           .eq(self.addr + 2),
                    begin_read          .eq(1),

                    self.cart.ad.o      .eq(result_data),
                    self.cart.ad.oe     .eq(1)         
                ]

        with m.FSM():
            with m.State('IDLE'):
                with m.If(self.valid & begin_read):
                    m.next = 'READ'

                    m.d.sync += [
                        begin_read      .eq(0),
                        self.bus.adr    .eq(self.addr[1:32]),
                        self.bus.cyc    .eq(1),
                        self.bus.stb    .eq(1),
                        self.bus.sel    .eq(3),                        
                    ]

            with m.State('READ'):
                with m.If(self.bus.ack):
                    m.next = 'IDLE'

                    m.d.sync += [
                        result_data     .eq(self.bus.dat_r),
                        self.bus.adr    .eq(0),
                        self.bus.cyc    .eq(0),
                        self.bus.stb    .eq(0),
                        self.bus.sel    .eq(0),
                    ]

        return m

class N64InitiatorTest(ModuleTestCase):
    FRAGMENT_UNDER_TEST = N64Initiator
    SYNC_CLOCK_FREQUENCY = 40e6 

    def traces_of_interest(self):
        return [
            self.dut.addr,
            self.dut.valid,

            self.dut.bus.adr,
            self.dut.bus.dat_w,
            self.dut.bus.dat_r,
            self.dut.bus.sel,
            self.dut.bus.cyc,
            self.dut.bus.stb,
            self.dut.bus.we,
            self.dut.bus.ack,

            self.dut.cart.ad.i,
            self.dut.cart.ad.o,
            self.dut.cart.ad.oe,
            self.dut.cart.ale_h,
            self.dut.cart.ale_l,
            self.dut.cart.read,
            self.dut.cart.write,
            self.dut.cart.reset
        ]

    def initialize_signals(self):
        yield self.dut.cart.ad.i    .eq(0)
        yield self.dut.cart.ale_h   .eq(0)
        yield self.dut.cart.ale_l   .eq(0)
        yield self.dut.cart.read    .eq(0)
        yield self.dut.cart.write   .eq(0)

    @sync_test_case
    def test_basic(self):
        yield from self.advance_cycles(2)

        # Latch address

        yield self.dut.cart.ad.i    .eq(0x8765)
        yield
        yield from self.pulse(self.dut.cart.ale_h)
        yield from self.advance_cycles(2)
        
        yield self.dut.cart.ad.i    .eq(0x4321)
        yield
        yield from self.pulse(self.dut.cart.ale_l)
        yield from self.advance_cycles(2)

        # First Fetch

        yield from self.wait_until(self.dut.bus.stb, timeout=10)
        yield self.dut.bus.dat_r    .eq(0xA514)
        yield self.dut.bus.ack      .eq(1)

        read1_addr = yield self.dut.bus.adr

        yield
        yield self.dut.bus.dat_r    .eq(0)
        yield self.dut.bus.ack      .eq(0)
        yield

        # First Read (begins)

        yield self.dut.cart.read    .eq(1)
        yield from self.advance_cycles(2)

        # Second Fetch (interleaved)

        yield from self.wait_until(self.dut.bus.stb, timeout=10)
        yield self.dut.bus.dat_r    .eq(0xB3E2)
        yield self.dut.bus.ack      .eq(1)

        read2_addr = yield self.dut.bus.adr

        yield     
        yield self.dut.bus.dat_r    .eq(0)
        yield self.dut.bus.ack      .eq(0)
        yield

        # First Read (ends)

        read1_data = yield self.dut.cart.ad.o
        read1_oe   = yield self.dut.cart.ad.oe

        yield self.dut.cart.read    .eq(0)
        yield from self.advance_cycles(5)

        # Second Read

        yield self.dut.cart.read    .eq(1)
        yield from self.advance_cycles(2)

        read2_data = yield self.dut.cart.ad.o
        read2_oe   = yield self.dut.cart.ad.oe

        yield self.dut.cart.read    .eq(0)
        yield from self.advance_cycles(2)

        # Assertions

        self.assertEqual(read1_addr, 0x87654321)
        self.assertEqual(read1_data, 0xA514)
        self.assertEqual(read1_oe,   1)

        self.assertEqual(read2_addr, 0x87654322)
        self.assertEqual(read2_data, 0xB3E2)
        self.assertEqual(read2_oe,   1)
