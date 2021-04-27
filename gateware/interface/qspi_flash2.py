from nmigen import *
from nmigen.hdl.rec import DIR_FANIN, DIR_FANOUT
from nmigen.utils import log2_int

from nmigen_soc import wishbone
from nmigen_soc.memory import MemoryMap

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

        self.start      = Signal()
        self.address    = Signal(24)

        self.idle       = Signal()
        self.valid      = Signal()
        self.data       = Signal(32)

        self._in_shift  = Signal(32)
        self._out_shift = Signal(32)
        self._counter   = Signal(3)

    def elaborate(self, platform):
        m = Module()

        cs = Signal()

        m.d.sync += [
            self._in_shift[4:]      .eq(self._in_shift[:28]),
            self._out_shift[4:]     .eq(self._out_shift[:28]),
            self._in_shift[0:4]     .eq(self.bus.d.i),
            self._out_shift[0:4]    .eq(0),

            self.valid              .eq(0),
        ]

        m.d.comb += [
            self.bus.d.o            .eq(self._out_shift[28:32]),
            self.data               .eq(self._in_shift),

            self.bus.cs_n           .eq(~cs),
            self.idle               .eq(0),
        ]

        with m.If(self._counter > 0):
            m.d.sync += [
                self._counter       .eq(self._counter - 1)
            ]

        current_address     = Signal(24)

        with m.FSM():

            with m.State("INITIAL"):
                m.next = "STARTUP"
                m.d.sync += self._counter       .eq(7)

            with m.State("STARTUP"):
                with m.If(self._counter == 0):
                    m.next = "IDLE"

            with m.State("IDLE"):
                m.d.comb += self.idle           .eq(1)

                with m.If(self.start):
                    m.next = "START"
                    m.d.sync += [
                        current_address         .eq(self.address),
                    ]

            with m.State("START"):
                m.next = "COMMAND"                    
                m.d.sync += [
                    self._counter               .eq(7),
                    self._out_shift             .eq(0x11101011),
                    self.bus.d.oe               .eq(0x1),

                    cs                          .eq(1),
                    self.bus.sck                .eq(1),
                ]

            with m.State("COMMAND"):
                with m.If(self._counter == 0):
                    m.next = "ADDRESS"
                    m.d.sync += [                 
                        self._counter           .eq(7),
                        self._out_shift[8:32]   .eq(current_address),
                        self._out_shift[0:8]    .eq(0xF0),
                        self.bus.d.oe           .eq(0xF),
                    ]

            with m.State("ADDRESS"):
                with m.If(self._counter == 0):
                    m.next = "DUMMY"
                    m.d.sync += [
                        self._counter           .eq(3), 
                        self.bus.d.oe           .eq(0x0),
                    ]

            with m.State("DUMMY"):
                with m.If(self._counter == 0):
                    m.next = "DATA"
                    m.d.sync += [
                        self._counter           .eq(7),
                    ]   

            with m.State("DATA"):
                with m.If(self._counter == 0):
                    m.next = "WAITING"
                    m.d.sync += [                        
                        self.valid              .eq(1),
                        self.bus.sck            .eq(0),
                    ]

            with m.State("WAITING"):
                m.d.comb += self.idle           .eq(1)

                with m.If(self.start):
                    m.d.sync += [
                        current_address         .eq(self.address),
                    ]                    

                    with m.If(self.address == current_address + 1):
                        m.next = "DATA"
                        m.d.sync += [
                            self._counter       .eq(7),
                            self.bus.sck        .eq(1),
                        ]
                    with m.Else():
                        m.next = "RECOVERY"
                        m.d.sync += [
                            self._counter       .eq(7),
                            cs                  .eq(0),
                        ]

            with m.State("RECOVERY"):
                with m.If(self._counter == 0):
                    m.next = "START"

        return m


class QSPIFlashWishboneInterface(Elaboratable):

    def __init__(self):
        self.bus = QSPIBus()
        self.wb = wishbone.Interface(addr_width=24, data_width=32, granularity=8, features={"stall"})

        size = 2**26
        granularity = 8

        map = MemoryMap(addr_width=log2_int(size), data_width=granularity)
        map.add_resource(self, size=size)
        self.wb.memory_map = map

    def elaborate(self, platform):
        m = Module()

        m.submodules.interface = interface = QSPIFlashInterface()

        m.d.comb += [
            interface.bus           .connect(self.bus),

            interface.start         .eq(self.wb.cyc & self.wb.stb),
            interface.address       .eq(self.wb.adr),

            self.wb.stall           .eq(~interface.idle),
            self.wb.dat_r           .eq(interface.data),
            self.wb.ack             .eq(interface.valid),
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
            self.dut.idle,
            self.dut.valid,
            self.dut.data,

            self.dut._in_shift,
            self.dut._out_shift,
            self.dut._counter,
        ]    

    @sync_test_case
    def test_basic(self):
        yield from self.advance_cycles(10)

        #

        yield self.dut.address.eq(0x876543)
        yield self.dut.start.eq(1)
        yield
        yield self.dut.start.eq(0)
        yield

        yield from self.advance_cycles(20)

        for x in [0xF, 0xE, 0xD, 0xC, 0xB, 0xA, 0x9, 0x8]:
            yield self.dut.bus.d.i.eq(x)
            yield

        yield self.dut.bus.d.i.eq(0)
        yield

        yield from self.advance_cycles(5)

        #

        yield self.dut.address.eq(0x876544)
        yield self.dut.start.eq(1)
        yield
        yield self.dut.start.eq(0)        

        for x in [0x7, 0x6, 0x5, 0x4, 0x3, 0x2, 0x1, 0x0]:
            yield self.dut.bus.d.i.eq(x)
            yield

        yield self.dut.bus.d.i.eq(0)
        yield

        yield from self.advance_cycles(5)

        #

        yield self.dut.address.eq(0x876546)
        yield self.dut.start.eq(1)
        yield
        yield self.dut.start.eq(0)
        yield

        yield from self.advance_cycles(28)

        for x in [0xC, 0xA, 0xF, 0xE, 0xB, 0xA, 0xB, 0xE]:
            yield self.dut.bus.d.i.eq(x)
            yield

        yield self.dut.bus.d.i.eq(0)
        yield

        yield from self.advance_cycles(20) 


class QSPIFlashWishboneInterfaceTest(ModuleTestCase):
    FRAGMENT_UNDER_TEST = QSPIFlashWishboneInterface

    def traces_of_interest(self):
        return [
            self.dut.bus.sck,
            self.dut.bus.cs_n,
            self.dut.bus.d.i,
            self.dut.bus.d.o,
            self.dut.bus.d.oe,

            self.dut.wb.cyc,
            self.dut.wb.stb,
            self.dut.wb.stall,
            self.dut.wb.ack,
            self.dut.wb.adr,
            self.dut.wb.dat_r
        ]

    @sync_test_case
    def test_basic(self):
        yield from self.advance_cycles(10)

        #

        yield self.dut.wb.adr.eq(0x876543)
        yield self.dut.wb.cyc.eq(1)
        yield self.dut.wb.stb.eq(1)
        yield
        yield self.dut.wb.stb.eq(0)
        yield

        yield from self.advance_cycles(20)

        for x in [0xF, 0xE, 0xD, 0xC, 0xB, 0xA, 0x9, 0x8]:
            yield self.dut.bus.d.i.eq(x)
            yield

        yield self.dut.bus.d.i.eq(0)
        yield        

        yield self.dut.wb.cyc.eq(0)
        yield

        yield from self.advance_cycles(5)


        #

        yield self.dut.wb.adr.eq(0x876544)
        yield self.dut.wb.cyc.eq(1)
        yield self.dut.wb.stb.eq(1)
        yield
        yield self.dut.wb.stb.eq(0)   

        for x in [0x7, 0x6, 0x5, 0x4, 0x3, 0x2, 0x1, 0x0]:
            yield self.dut.bus.d.i.eq(x)
            yield

        yield self.dut.bus.d.i.eq(0)
        yield

        yield self.dut.wb.cyc.eq(0)
        yield

        yield from self.advance_cycles(5)

        #

        yield self.dut.wb.adr.eq(0x876546)
        yield self.dut.wb.cyc.eq(1)
        yield self.dut.wb.stb.eq(1)
        yield
        yield self.dut.wb.stb.eq(0)
        yield

        yield from self.advance_cycles(28)

        for x in [0xC, 0xA, 0xF, 0xE, 0xB, 0xA, 0xB, 0xE]:
            yield self.dut.bus.d.i.eq(x)
            yield

        yield self.dut.bus.d.i.eq(0)
        yield

        yield self.dut.wb.cyc.eq(0)
        yield

        yield from self.advance_cycles(20)
