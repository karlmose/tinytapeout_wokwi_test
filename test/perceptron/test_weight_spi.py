"""RAM interface SPI master unit tests — verifies read/write bit patterns."""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, FallingEdge

CMD_READ  = 0x03
CMD_WRITE = 0x02


async def do_start(dut):
    clock = Clock(dut.clk, 10, unit="ns")  # 100 MHz sim clock
    cocotb.start_soon(clock.start())

    dut.rst_n.value = 0
    dut.addr.value = 0
    dut.start_read.value = 0
    dut.inc.value = 0
    dut.dec.value = 0
    dut.spi_miso.value = 0
    dut.cs_wait_cycles.value = 8     # Match default
    dut.spi_clk_div.value = 2       # div-by-8 (match default)

    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 20)

    assert dut.spi_cs.value == 1, "CS should be high after reset"


async def expect_spi_transfer(dut, byte_val):
    for i in range(8):
        await RisingEdge(dut.spi_sck)
        expected_bit = (byte_val >> (7-i)) & 1
        assert dut.spi_mosi.value == expected_bit, \
            f"Bit {7-i} of byte 0x{byte_val:02x} mismatch: got {dut.spi_mosi.value}, expected {expected_bit}"
        await FallingEdge(dut.spi_sck)


@cocotb.test()
async def test_read_operation(dut):
    """Verify READ command sends correct CMD + ADDR, receives data byte."""
    await do_start(dut)

    addr = 0x1234

    dut.addr.value = addr
    dut.start_read.value = 1
    await ClockCycles(dut.clk, 1)
    dut.start_read.value = 0

    await FallingEdge(dut.spi_cs)

    await expect_spi_transfer(dut, CMD_READ)
    await expect_spi_transfer(dut, (addr >> 8) & 0xFF)
    await expect_spi_transfer(dut, addr & 0xFF)

    expected_data = 0xA5
    for i in range(8):
        bit = (expected_data >> (7-i)) & 1
        dut.spi_miso.value = bit
        await RisingEdge(dut.spi_sck)
        assert dut.spi_mosi.value == 0, f"Data phase MOSI bit {7-i} should be 0"
        await FallingEdge(dut.spi_sck)

    await RisingEdge(dut.spi_cs)
    await ClockCycles(dut.clk, 20)
    assert dut.read_valid.value == 1, "read_valid should be high"
    assert dut.weight.value == expected_data, \
        f"Read weight should be 0x{expected_data:02x}, got 0x{dut.weight.value:02x}"


@cocotb.test()
async def test_update_operation(dut):
    """Verify READ then INCREMENT writes back value+1."""
    await do_start(dut)

    addr = 0x0ABC
    initial_val = 0x10

    dut.addr.value = addr
    dut.start_read.value = 1
    await ClockCycles(dut.clk, 1)
    dut.start_read.value = 0

    await FallingEdge(dut.spi_cs)

    for _ in range(24):
        await FallingEdge(dut.spi_sck)

    for i in range(8):
        dut.spi_miso.value = (initial_val >> (7-i)) & 1
        await RisingEdge(dut.spi_sck)
        await FallingEdge(dut.spi_sck)

    await RisingEdge(dut.spi_cs)
    await ClockCycles(dut.clk, 20)
    assert dut.read_valid.value == 1
    assert dut.weight.value == initial_val

    await ClockCycles(dut.clk, 20)

    dut.inc.value = 1
    await ClockCycles(dut.clk, 1)
    dut.inc.value = 0

    if dut.spi_cs.value == 1:
        await FallingEdge(dut.spi_cs)

    await expect_spi_transfer(dut, CMD_WRITE)
    await expect_spi_transfer(dut, (addr >> 8) & 0xFF)
    await expect_spi_transfer(dut, addr & 0xFF)

    expected_new_val = initial_val + 1
    await expect_spi_transfer(dut, expected_new_val)

    await RisingEdge(dut.spi_cs)
    await ClockCycles(dut.clk, 20)
    assert dut.write_done.value == 1, "write_done should be asserted"
