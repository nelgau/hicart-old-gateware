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

        # self.wb = wishbone.Interface(addr_width=24, data_width=32, features={"stall"})

        self.start      = Signal()
        self.address    = Signal(24)

        self.ready      = Signal()
        self.valid      = Signal()
        self.data       = Signal(32)

        self._in_shift  = Signal(32)
        self._out_shift = Signal(32)
        self._counter   = Signal(3)

    def elaborate(self, platform):
        m = Module()

        m.d.comb += [
            self.ready.eq(0)
        ]

        m.d.sync += [
            self.valid.eq(0)
        ]

        current_address     = Signal(24)
        sequential_address  = Signal(24)

        with m.FSM():

            with m.State("IDLE"):
                m.d.comb += self.ready.eq(1)

                with m.If(self.start):
                    m.next = "START"
                    m.d.sync += [
                        current_address         .eq(self.address),
                        sequential_address      .eq(self.address + 1)
                    ]

            with m.State("START"):
                    m.next = "COMMAND"                    
                    m.d.sync += [
                        self._counter           .eq(7),
                        self._out_shift         .eq(0x11101011),
                        self.bus.d.oe           .eq(1),
                        
                    ]

            with m.State("COMMAND"):
                with m.If(self._counter == 0):
                    m.next = "ADDRESS"
                    m.d.sync += [
                        self._counter           .eq(7),
                        self._out_shift[8:32]   .eq(0x654321),
                        self._out_shift[0:8]    .eq(0xF0),                        
                    ]

            with m.State("ADDRESS"):
                with m.If(self._counter == 0):
                    m.next = "DUMMY"
                    m.d.sync += [
                        self._counter           .eq(3),
                        self.bus.d.oe           .eq(0),                        
                    ]

            with m.State("DUMMY"):
                with m.If(self._counter == 0):
                    m.next = "DATA"
                    m.d.sync += [
                        self._counter           .eq(7),
                    ]   

            with m.State("DATA"):
                with m.If(self._counter == 0):
                    m.d.comb += self.ready.eq(1)

                    m.next = "IDLE"
                    m.d.sync += [                        
                        self.valid              .eq(1),
                    ]


        with m.If(self._counter != 0):
            m.d.sync += [
                self._counter           .eq(self._counter - 1),                
                self._out_shift[4:]     .eq(self._out_shift[:28]),                
                self._out_shift[0:4]    .eq(0),
            ]
        
        m.d.sync += [            
            self._in_shift[4:]          .eq(self._in_shift[:28]),
            self._in_shift[0:4]         .eq(self.bus.d.i),
        ]

        m.d.comb += [
            self.bus.d.o                .eq(self._out_shift[28:32]),
            self.data                   .eq(self._in_shift),

        ]

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

            self.dut.start,
            self.dut.address,
            self.dut.ready,
            self.dut.valid,
            self.dut.data,

            self.dut._in_shift,
            self.dut._out_shift,
            self.dut._counter,
        ]    

    @sync_test_case
    def test_basic(self):
        yield self.dut.address.eq(0x654321)
        yield

        yield self.dut.start.eq(1)
        yield
        yield self.dut.start.eq(0)
        yield

        yield from self.advance_cycles(20)

        for x in [0xF, 0xE, 0xD, 0xC, 0xB, 0xA, 0x9, 0x8]:
            yield self.dut.bus.d.i.eq(x)
            yield

        yield from self.advance_cycles(5)



