import struct
import itertools

from nmigen import *
from nmigen.build import *
from nmigen_soc import wishbone

from n64.cic import CIC
from n64.pi import PIWishboneInitiator
from interface.qspi_flash import QSPIFlashWishboneInterface
from utils.cli import main_runner


class Top(Elaboratable):

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

        m.submodules.car                               = platform.clock_domain_generator()
        m.submodules.flash_connector = flash_connector = platform.flash_connector()

        m.submodules.cic        = self.cic = cic       = DomainRenamer("cic")(CIC())
        m.submodules.initiator  = self.initiator       = initiator       = PIWishboneInitiator();
        m.submodules.qspi_flash = self.flash_interface = flash_interface = QSPIFlashWishboneInterface()

        # rom_size = 16384

        # with open("../roms/sm64.z64", "rb") as f:
        #     rom_bytes = f.read()[0:16384]
        #     rom_data = [x[0] for x in struct.iter_unpack('>L', rom_bytes)]

        # m.submodules.sram = self.sram = sram = SRAMPeripheral(size=rom_size, data_width=32, writable=False)

        # sram.init = rom_data


        decoder = wishbone.Decoder(addr_width=32, data_width=32, granularity=8, features={"stall"})
        # decoder.add(sram.bus, addr=0x10000000)

        decoder.add(flash_interface.bus, addr=0x10000000)

        m.submodules.decoder = decoder


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
            initiator.bus           .connect(decoder.bus),

            flash_interface.qspi         .connect(flash_connector.qspi),            

            initiator.ad16.ad.i     .eq( n64_cart.ad.i  ),
            initiator.ad16.ale_h    .eq( n64_cart.ale_h ),
            initiator.ad16.ale_l    .eq( n64_cart.ale_l ),
            initiator.ad16.read     .eq( n64_cart.read  ),
            initiator.ad16.write    .eq( n64_cart.write ),

            n64_cart.ad.o           .eq( initiator.ad16.ad.o  ),
            n64_cart.ad.oe          .eq( initiator.ad16.ad.oe ),

            pmod.d.oe               .eq(1)
        ]

        self.probe_qspi_flash(m)

        return m

    def probe_initiator_addr(self, m):
        initiator = self.initiator
        pmod = self.pmod
        m.d.comb += pmod.d.o.eq(initiator.bus.adr[0:8])

    def probe_initiator_bus(self, m):
        initiator = self.initiator
        flash_interface = self.flash_interface
        pmod = self.pmod
        m.d.comb += [
            pmod.d.o[0].eq(initiator.bus.cyc),
            pmod.d.o[1].eq(initiator.bus.stb),
            pmod.d.o[2].eq(initiator.bus.stall),
            pmod.d.o[3].eq(initiator.bus.ack),

            pmod.d.o[4].eq(flash_interface.bus.cyc),
            pmod.d.o[5].eq(flash_interface.bus.stb),
            pmod.d.o[6].eq(flash_interface.bus.stall), 
            pmod.d.o[7].eq(flash_interface.bus.ack), 
        ]

    def probe_qspi_flash(self, m):
        flash_interface = self.flash_interface
        pmod = self.pmod
        m.d.comb += [
            pmod.d.o[0].eq(ClockSignal('sync')),
            pmod.d.o[1].eq(flash_interface.qspi.sck),
            pmod.d.o[2].eq(flash_interface.qspi.cs_n),
            pmod.d.o[3].eq(flash_interface.qspi.d.o[0]),
            pmod.d.o[4].eq(flash_interface.qspi.d.o[1]),
            pmod.d.o[5].eq(flash_interface.qspi.d.o[2]),
            pmod.d.o[6].eq(flash_interface.qspi.d.o[3]),
            pmod.d.o[7].eq(flash_interface.qspi.d.oe[0]),
        ]

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
