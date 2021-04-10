import os
import subprocess

from nmigen import *
from nmigen.build import *
from nmigen.vendor.lattice_ecp5 import *
from nmigen_boards.resources import *

__all__ = ["HomeInvaderRevAPlatform"]

class HomeInvaderRevADomainGenerator(Elaboratable):
    """ Clock generator for Rev A boards. """

    def __init__(self, *, clock_frequencies=None, clock_signal_name=None):
        pass

    def elaborate(self, platform):
        m = Module()

        # Grab our default input clock.
        input_clock = platform.request(platform.default_clk, dir="i")        

        # Create our domains; but don't do anything else for them, for now.
        m.domains.sync = ClockDomain()
        m.domains.cic  = ClockDomain()

        locked = Signal()
        clk40  = Signal()
        clk20  = Signal()

        m.submodules.pll = Instance("EHXPLLL",
                # Clock in
                i_CLKI=input_clock,

                # Generated clock outputs.
                o_CLKOP=clk40,
                o_CLKOS=clk20,

                # Status
                o_LOCK=locked,

                # PLL parameters
                p_PLLRST_ENA="DISABLED",
                p_INTFB_WAKE="DISABLED",
                p_STDBY_ENABLE="DISABLED",
                p_DPHASE_SOURCE="DISABLED",
                p_OUTDIVIDER_MUXA="DIVA",
                p_OUTDIVIDER_MUXB="DIVB",
                p_OUTDIVIDER_MUXC="DIVC",
                p_OUTDIVIDER_MUXD="DIVD",
                p_CLKI_DIV = 3,
                p_CLKOP_ENABLE = "ENABLED",
                p_CLKOP_DIV = 15,
                p_CLKOP_CPHASE = 7,
                p_CLKOP_FPHASE = 0,
                p_CLKOS_ENABLE = "ENABLED",
                p_CLKOS_DIV = 30,
                p_CLKOS_CPHASE = 7,
                p_CLKOS_FPHASE = 0,
                p_FEEDBK_PATH = "CLKOP",
                p_CLKFB_DIV = 10,

                # Internal feedback
                i_CLKFB=clk40,

                # Control signals
                i_RST=0,
                i_STDBY=0,
                i_PHASESEL0=0,
                i_PHASESEL1=0,
                i_PHASEDIR=1,
                i_PHASESTEP=1,
                i_PHASELOADREG=1,
                i_PLLWAKESYNC=0,

                # Output Enables.
                i_ENCLKOP=0,
                i_ENCLKOS=0,

                # Synthesis attributes.
                a_FREQUENCY_PIN_CLKI="12",
                a_FREQUENCY_PIN_CLKOP="40",
                a_FREQUENCY_PIN_CLKOS="20",
                a_ICP_CURRENT="12",
                a_LPF_RESISTOR="8",
                a_MFG_ENABLE_FILTEROPAMP="1",
                a_MFG_GMCREF_SEL="2"
        )

        m.d.comb += [
            ClockSignal("sync")    .eq(clk40),
            ClockSignal("cic")     .eq(clk20),

            ResetSignal("sync")    .eq(~locked),
            ResetSignal("cic")     .eq(~locked)
        ]

        return m

class HomeInvaderRevAPlatform(LatticeECP5Platform):
    device      = "LFE5U-12F"
    package     = "BG256"
    speed       = "6"
    default_clk = "clk12"

    clock_domain_generator = HomeInvaderRevADomainGenerator
    
    resources = [
        Resource("clk12", 0, Pins("J16", dir="i"), 
            Clock(12e6), Attrs(IO_TYPE="LVCMOS33")),

        Resource("n64_cart", 0,
            Subsignal("ad",       Pins("A2 A3 A4 A5 A8 A9 A10 A11 B12 B11 B10 B9 B6 B5 B4 B3", dir="io"),
                Attrs(PULLMODE="DOWN")),

            Subsignal("ale_h",    PinsN("A7", dir="i"),  Attrs(PULLMODE="UP")),
            Subsignal("ale_l",    PinsN("A6", dir="i"),  Attrs(PULLMODE="UP")),
            Subsignal("read",     PinsN("B8", dir="i"),  Attrs(PULLMODE="UP")),
            Subsignal("write",    PinsN("B7", dir="i"),  Attrs(PULLMODE="UP")),

            Subsignal("s_clk",    Pins("A13", dir="i")),
            Subsignal("s_data",   Pins("B14", dir="io"), Attrs(PULLMODE="NONE")),

            Subsignal("cic_dclk", Pins("A12", dir="i")),
            Subsignal("cic_data", Pins("B13", dir="io"), Attrs(PULLMODE="NONE")),

            Subsignal("reset",    PinsN("A14", dir="i"), Attrs(PULLMODE="UP")),
            Subsignal("nmi",      PinsN("C13", dir="i"), Attrs(PULLMODE="UP")),

            Attrs(IO_TYPE="LVCMOS33", SLEWRATE="SLOW")
        ),

        Resource("usb_fifo", 0,
            Subsignal("d",        Pins("L15 M16 M15 N16 N14 P16 P15 R16", dir="io")),
            Subsignal("rxf",      Pins("R15", dir="i"), Attrs(PULLMODE="NONE")),
            Subsignal("txe",      Pins("T15", dir="i"), Attrs(PULLMODE="NONE")),
            Subsignal("rd",       Pins("R14", dir="o")),
            Subsignal("wr",       Pins("T14", dir="o")),
            Subsignal("siwu",     Pins("R13", dir="o")),

            # Only used in synchronous mode.
            Subsignal("clkout",   Pins("L16", dir="i")),
            Subsignal("oe",       Pins("T13", dir="o"))
        ),

        Resource("pmod", 0,
            Subsignal("d",        Pins("C4 C5 C6 C7 D4 D5 D6 D7", dir="io"))
        ),

        *LEDResources(pins="C16 B16 C15 B15 E15 C14 D14 E14",
            attrs=Attrs(IO_TYPE="LVCMOS33")),
    ]

    connectors = [
        Connector("pmod", 0, "C4 C5 C6 C7 - - D4 D5 D6 D7 - -")
    ]

    @property
    def required_tools(self):
        return super().required_tools + [
          "ecpprog"
        ]

    def toolchain_prepare(self, fragment, name, **kwargs):
        overrides = dict(ecppack_opts="--compress --freq 38.8")
        overrides.update(kwargs)
        return super().toolchain_prepare(fragment, name, **overrides)

    def toolchain_program(self, products, name):
        ecpprog = os.environ.get("ECPPROG", "ecpprog")
        with products.extract("{}.bit".format(name)) as bitstream_filename:
            subprocess.check_call([ecpprog, "-d", "s:0x0403:0x6010:FT5YLSVU", "-I", "B", "-S", bitstream_filename])

if __name__ == "__main__":
    from nmigen_boards.test.blinky import *
    HomeInvaderRevAPlatform().build(Blinky(), do_program=True)
