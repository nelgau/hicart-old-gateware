import struct
import itertools

from nmigen import *
from nmigen.build import *
from lambdasoc.periph.sram import SRAMPeripheral

from debug.ila import HomeInvaderILA, HomeInvaderILAFrontend
from n64.cic import CIC
from n64.pi import PIInitiator
from utils.cli import main_runner


class Top(Elaboratable):

    def __init__(self):
        pass

        # self.ila = HomeInvaderILA(
        #     sample_depth=32,
        #     signals=[
        #         self.counter,
        #         self.hello
        #     ]
        # )    

    # def interactive_display(self):
    #     frontend = HomeInvaderILAFrontend(ila=self.ila)
    #     frontend.interactive_display()    

    def elaborate(self, platform):
        m = Module()

        def get_all_resources(name):
            resources = []
            for number in itertools.count():
                try:
                    resources.append(platform.request(name, number))
                except ResourceError:
                    break
            return resources

        leds = get_all_resources('led')
        leds = Cat([l.o for l in leds])

        m.submodules.car       = platform.clock_domain_generator()
        m.submodules.cic       = self.cic = cic = CIC()
        m.submodules.initiator = self.initiator = initiator = PIInitiator();

        rom_size = 16384

        with open("../roms/nc99.n64", "rb") as f:
            rom_bytes = f.read()[0:16384]
            rom_data = [x[0] for x in struct.iter_unpack('<L', rom_bytes)]

        m.submodules.sram = sram = SRAMPeripheral(size=rom_size, data_width=32, writable=False)

        sram.init = rom_data

        n64_cart = self.n64_cart = platform.request('n64_cart')
        pmod     = self.pmod     = platform.request('pmod')

        m.d.comb += [
            cic.reset               .eq( n64_cart.reset      ),
            cic.data_clk            .eq( n64_cart.cic_dclk   ),
            cic.data_i              .eq( n64_cart.cic_data.i ),

            n64_cart.cic_data.o     .eq( cic.data_o  ),
            n64_cart.cic_data.oe    .eq( cic.data_oe ),
        ]

        m.d.comb += [
            initiator.bus.connect(sram.bus),

            initiator.ad16.ad.i     .eq( n64_cart.ad.i  ),
            initiator.ad16.ale_h    .eq( n64_cart.ale_h ),
            initiator.ad16.ale_l    .eq( n64_cart.ale_l ),
            initiator.ad16.read     .eq( n64_cart.read  ),
            initiator.ad16.write    .eq( n64_cart.write ),

            n64_cart.ad.o           .eq( initiator.ad16.ad.o  ),
            n64_cart.ad.oe          .eq( initiator.ad16.ad.oe ),

            pmod.d.oe               .eq(1)
        ]

        self.probe_cic(m)



        # sync_clk = ClockSignal()
        # spi_clk = Signal()
        # spi_en = Signal()

        # m.submodules += Instance("USRMCLK",
        #         i_USRMCLKI=spi_clk,
        #         i_USRMCLKTS=Signal()
        #     )

        # m.d.sync += [
        #     spi_en      .eq( ~spi_en )
        # ]

        # m.d.comb += [
        #     spi_clk     .eq( ~(spi_en & sync_clk ) ),
        #     # spi_clk     .eq( sync_clk ),

        #     pmod.d.o[0] .eq( spi_en ),
        #     pmod.d.o[1] .eq( sync_clk ),

        # ]

        return m

    def probe_initiator_addr(self, m):
        initiator = self.initiator
        pmod = self.pmod
        m.d.comb += pmod.d.o.eq(initiator.addr[1:9])

    def probe_bus_states(self, m):
        n64_cart = self.n64_cart
        pmod = self.pmod
        m.d.comb += [
            pmod.d.o[0].eq(n64_cart.cic_data.i),
            pmod.d.o[1].eq(n64_cart.read),            
            pmod.d.o[2].eq(n64_cart.ale_l),
            pmod.d.o[3].eq(n64_cart.ale_h),
            pmod.d.o[4].eq(n64_cart.ad.i[15]),
            pmod.d.o[5].eq(n64_cart.ad.i[14]),
            pmod.d.o[6].eq(n64_cart.ad.i[13]),
            pmod.d.o[7].eq(n64_cart.ad.i[12]),
        ]

    def probe_cic(self, m):
        n64_cart = self.n64_cart
        pmod = self.pmod
        m.d.comb += [
            pmod.d.o[0].eq(n64_cart.cic_dclk),
            pmod.d.o[1].eq(n64_cart.cic_data.i),
            pmod.d.o[2].eq(n64_cart.read),          
            pmod.d.o[3].eq(n64_cart.ale_l),
            pmod.d.o[4].eq(n64_cart.ale_h),
            pmod.d.o[5].eq(n64_cart.ad.i[15]),
            pmod.d.o[6].eq(n64_cart.ad.i[14]),
            pmod.d.o[7].eq(n64_cart.ad.i[13]),
        ]

    def probe_ad_low(self, m):
        n64_cart = self.n64_cart
        pmod = self.pmod
        m.d.comb += [
            pmod.d.o.eq(n64_cart.ad.i[8:16]),
        ]

    def probe_ad_high(self, m):
        n64_cart = self.n64_cart
        pmod = self.pmod
        m.d.comb += [
            pmod.d.o.eq(n64_cart.ad.i[8:16]),
        ]

if __name__ == "__main__":
    main_runner(Top())
