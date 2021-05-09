from nmigen import *
from nmigen.sim import *
from nmigen.utils import log2_int
from nmigen_soc.memory import MemoryMap
from nmigen_soc.wishbone import Interface

from test import *
from test.driver.wishbone import WishboneInitiator
from test.emulator.wishbone import WishboneEmulator


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

        stb_counter = Signal(range(ratio))
        ack_counter = Signal(range(ratio))

        #
        # Control Path
        # 

        with m.FSM() as fsm:

            m.d.comb += [
                self.bus.stall.eq(~fsm.ongoing("IDLE") & ~self.bus.ack),                
            ]

            with m.State("IDLE"):
                with m.If(self.bus.cyc & self.bus.stb):
                    m.next = "SENDING"

            with m.State("SENDING"):
                m.d.comb += self.sub_bus.cyc.eq(1)
                m.d.comb += self.sub_bus.stb.eq(1)

                with m.If(~self.sub_bus.stall):

                    with m.If(stb_counter == (ratio - 1)):
                        m.next = "WAITING"

            with m.State("WAITING"):
                m.d.comb += self.sub_bus.cyc.eq(1)

                with m.If(self.sub_bus.ack):
                    with m.If(ack_counter == (ratio - 1)):
                        m.d.comb += self.bus.ack.eq(1)

                        m.next = "IDLE"

                        with m.If(self.bus.cyc & self.bus.stb):
                            m.next = "SENDING"                


        # Counters

        with m.If(self.sub_bus.cyc & self.sub_bus.stb & ~self.sub_bus.stall):
            m.d.sync += stb_counter.eq(stb_counter + 1)

        with m.If(self.sub_bus.ack):
            m.d.sync += ack_counter.eq(ack_counter + 1)

        with m.If(self.bus.cyc & self.bus.stb & ~self.bus.stall):
            m.d.sync += stb_counter.eq(0)
            m.d.sync += ack_counter.eq(0)

        #
        # Data Path
        #

        # Address

        address = Signal(self.addr_width, reset_less=True)

        with m.If(self.bus.cyc & self.bus.stb & ~self.bus.stall):
            m.d.sync += address.eq(self.bus.adr)

        m.d.comb += self.sub_bus.adr.eq(Cat(stb_counter, address))            

        # Write

        m.d.comb += self.sub_bus.dat_w.eq(self.bus.word_select(stb_counter, dw_to))

        # Read

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
        sub_bus.memory_map = MemoryMap(addr_width=24, data_width=8)

        dut = DownConverter(sub_bus=sub_bus, addr_width=22, data_width=32,
            granularity=8, features={"stall"})

        intr_driver = WishboneInitiator(dut.bus)
        sub_emulator = WishboneEmulator(sub_bus)

        def intr_process():
            yield

            yield from intr_driver.read_once(0x00040000)

            # yield dut.bus.cyc.eq(1)
            # yield dut.bus.stb.eq(1)
            # yield dut.bus.adr.eq(0x00040000)
            # yield dut.bus.we.eq(0)
            # yield

            # yield dut.bus.stb.eq(0)
            # yield

            # for i in range(3):
            #     yield

            # yield dut.bus.stb.eq(1)
            # yield

            # yield dut.bus.stb.eq(0)
            # yield

            # for i in range(4):
            #     yield

            # yield dut.bus.cyc.eq(0)
            # yield            

        def sub_process():
            yield Passive()
            yield from sub_emulator.emulate()

            # delay = 2
            # max_outstanding = 2

            # counter = 0
            # pipeline = [0 for _ in range(delay)]
            # stalled = False

            # while True:
            #     did_accept = (yield sub_bus.cyc & sub_bus.stb) and not stalled

            #     accept_adr = yield sub_bus.adr
            #     accept_dat_w = yield sub_bus.dat_w
            #     accept_we = yield sub_bus.we 

            #     pipeline.append(did_accept)
            #     should_ack, pipeline = pipeline[0], pipeline[1:]

            #     stalled = sum(pipeline) >= max_outstanding

            #     yield sub_bus.dat_r.eq(counter)
            #     yield sub_bus.ack.eq(should_ack)
            #     yield sub_bus.stall.eq(stalled)
            #     yield

            #     if should_ack == 1:
            #         counter += 1

        with self.simulate(dut, traces=dut.ports()) as sim:
            sim.add_clock(1.0 / 100e6, domain='sync')
            sim.add_sync_process(intr_process)
            sim.add_sync_process(sub_process)
