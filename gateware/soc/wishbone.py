from nmigen import *
from nmigen.sim import *
from nmigen.utils import log2_int
from nmigen_soc.memory import MemoryMap
from nmigen_soc.wishbone import Interface

from test import *


class DownConverter(Elaboratable):

    def __init__(self, *, sub_bus, addr_width, data_width, granularity=None, features=frozenset()):
        if granularity is None:
            granularity  = data_width

        self.sub_bus = sub_bus

        self.addr_width  = addr_width
        self.data_width  = data_width
        self.granularity = granularity
        self.features    = set(features)

        self.bus = Interface(addr_width=addr_width, data_width=data_width,
            granularity=granularity, features=features)

        granularity_bits = log2_int(data_width // granularity)
        memory_map = MemoryMap(addr_width=max(1, addr_width + granularity_bits),
                               data_width=granularity)
        memory_map.add_window(sub_bus.memory_map)
        self.bus.memory_map = memory_map

    def elaborate(self, platform):
        m = Module()

        dw_from = len(self.bus.dat_w)
        dw_to   = len(self.sub_bus.dat_w)
        ratio   = dw_from // dw_to

        address = Signal(self.addr_width)
        counter = Signal(range(ratio))

        with m.FSM() as fsm:

            m.d.comb += [
                self.bus.stall.eq(~fsm.ongoing("IDLE")),
                self.sub_bus.adr.eq(Cat(counter, address)),
            ]

            with m.State("IDLE"):
                m.d.sync += counter.eq(0)
                with m.If(self.bus.cyc & self.bus.stb):
                    m.next = "BEGIN"
                    m.d.sync += [
                        address.eq(self.bus.adr)                        
                    ]

            with m.State("BEGIN"):
                m.d.comb += self.sub_bus.cyc.eq(1)
                m.d.comb += self.sub_bus.stb.eq(1)

                with m.If(~self.sub_bus.stall):
                    m.next = "WAIT"

            with m.State("WAIT"):
                m.d.comb += self.sub_bus.cyc.eq(1)

                with m.If(self.sub_bus.ack):
                    m.d.sync += counter.eq(counter + 1)
                    m.next = "BEGIN"

                    with m.If(counter == (ratio - 1)):
                        m.d.comb += self.bus.ack.eq(1)
                        m.next = "IDLE"

        # Write datapath
        m.d.comb += self.sub_bus.dat_w.eq(self.bus.word_select(counter, dw_to))

        # Read datapath
        dat_r = Signal(dw_from, reset_less=True)


        # m.d.comb += self.bus.dat_r.eq(Cat(dat_r[dw_to:], self.sub_bus.dat_r))          # Little Endian
        m.d.comb += self.bus.dat_r.eq(Cat(self.sub_bus.dat_r, dat_r[:dw_from - dw_to]))    # Big Endian


        with m.If(self.sub_bus.ack):
            m.d.sync += dat_r.eq(self.bus.dat_r)

        return m

    def ports(self):
        return [
            self.bus,
            self.sub_bus
        ]

class Translator(Elaboratable):
    pass

    # def __init__(self, *, sub_bus, base_addr, size, addr_width, features=frozenset()):
    #     self.sub_bus = sub_bus
    #     self.base_addr = base_addr
    #     self.size = size

    #     self.bus = Interface(addr_width=addr_width,
    #                          data_width=sub_bus.data_width,
    #                          granularity=sub_bus.granularity,
    #                          features=features) 

    #     self.bus.memory_map = self.sub_bus.memory_map

    # def elaborate(self, platform):
    #     m = Module()

    #     m.d.comb += [
    #         self.bus        .connect(self.sub_bus, exclude={"adr"}),
    #         self.bus.adr    .eq(self.sub_bus.adr + self.base_addr),
    #     ]

    #     return m

class DownConverterTest(MultiProcessTestCase):

    def test_simple(self):
        sub_bus = Interface(addr_width=24, data_width=8, features={"stall"})
        dut = DownConverter(sub_bus=sub_bus, addr_width=22, data_width=32, features={"stall"})

        def intr_process():
            yield

            yield dut.bus.cyc.eq(1)
            yield dut.bus.stb.eq(1)
            yield dut.bus.adr.eq(0x00040000)
            yield dut.bus.we.eq(0)
            yield

            yield dut.bus.stb.eq(0)
            yield

            for i in range(100):
                yield

        def sub_process():
            yield Passive()

            counter = 0

            while True:
                while not (yield sub_bus.cyc & sub_bus.stb):
                    yield

                yield sub_bus.stall.eq(1)

                for i in range(5):
                    yield
                
                yield sub_bus.dat_r.eq(counter)
                yield sub_bus.ack.eq(1)
                yield

                yield sub_bus.stall.eq(0)
                yield sub_bus.ack.eq(0)

                counter += 1

        with self.simulate(dut, traces=dut.ports()) as sim:
            sim.add_clock(1.0 / 100e6, domain='sync')
            sim.add_sync_process(intr_process)
            sim.add_sync_process(sub_process)
