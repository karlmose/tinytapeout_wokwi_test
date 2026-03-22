"""Configuration/control tests — CS wait, buffer reset, clock divisor."""

import cocotb
from cocotb.triggers import ClockCycles, RisingEdge, FallingEdge, Timer
from perceptron.helpers import (
    start_clocks, parse_read_response,
    set_ram, ram_addr, to_unsigned_8,
    OP_RESP_VALID, OP_RESP_INVALID,
)


async def _measure_ram_sck_period(dut, spi, index, ram_value):
    """Trigger a RAM read and measure the SCK period in ns."""
    set_ram(dut, ram_addr(0, index), to_unsigned_8(ram_value))
    await spi.cmd_add_weight(index)

    # Wait for RAM CS to go low (transaction starts)
    for _ in range(5000):
        await RisingEdge(dut.clk)
        if int(dut.ram_spi_cs.value) == 0:
            break

    # Measure one full SCK cycle: rising edge → next rising edge
    for _ in range(500):
        await RisingEdge(dut.clk)
        if int(dut.ram_spi_sck.value) == 1:
            break
    t0 = cocotb.utils.get_sim_time(units="ns")

    # Wait for falling edge
    for _ in range(500):
        await RisingEdge(dut.clk)
        if int(dut.ram_spi_sck.value) == 0:
            break

    # Wait for next rising edge
    for _ in range(500):
        await RisingEdge(dut.clk)
        if int(dut.ram_spi_sck.value) == 1:
            break
    t1 = cocotb.utils.get_sim_time(units="ns")

    # Drain the read result
    await spi.cmd_read_poll(max_attempts=20)
    return t1 - t0


async def _add_weight_and_verify(dut, spi, index, ram_value, max_attempts=20):
    """Set RAM, add weight, read back and verify the sum."""
    set_ram(dut, ram_addr(0, index), to_unsigned_8(ram_value))
    await spi.cmd_add_weight(index)
    opcode, _, sum_signed = await spi.cmd_read_poll(max_attempts=max_attempts)
    assert opcode == OP_RESP_VALID, f"Expected VALID, got {opcode:#x}"
    assert sum_signed == ram_value, f"Expected {ram_value}, got {sum_signed}"


@cocotb.test()
async def test_set_cs_wait(dut):
    """Set cs_wait to different values and verify operations still complete."""
    spi = await start_clocks(dut)

    # Default cs_wait=3: verify basic operation
    await _add_weight_and_verify(dut, spi, 0x50, 100)
    await spi.cmd_reset_buffer()
    await ClockCycles(dut.clk, 20)

    # Change cs_wait to 5, verify operation still works
    await spi.cmd_set_cs_wait(5)
    await ClockCycles(dut.clk, 10)
    await _add_weight_and_verify(dut, spi, 0x51, 42)
    await spi.cmd_reset_buffer()
    await ClockCycles(dut.clk, 20)

    # Change cs_wait to 0 (minimum), verify faster operation still works
    await spi.cmd_set_cs_wait(0)
    await ClockCycles(dut.clk, 10)
    await _add_weight_and_verify(dut, spi, 0x52, 77)


@cocotb.test()
async def test_reset_buffer(dut):
    spi = await start_clocks(dut)

    set_ram(dut, ram_addr(0, 0x50), to_unsigned_8(100))
    await spi.cmd_add_weight(0x50)

    opcode, _, sum_val = await spi.cmd_read_poll()
    assert opcode == OP_RESP_VALID
    assert sum_val == 100, f"Expected 100 before reset, got {sum_val}"

    await spi.cmd_reset_buffer()
    await ClockCycles(dut.clk, 20)

    resp = await spi.cmd_read_raw()
    opcode, _, _ = parse_read_response(resp)
    assert opcode == OP_RESP_INVALID, f"Expected INVALID after reset, got {opcode:#x}"


@cocotb.test()
async def test_set_cs_wait_boundaries(dut):
    """Verify operations complete correctly at cs_wait boundary values."""
    spi = await start_clocks(dut)

    # cs_wait = 0 (minimum delay)
    await spi.cmd_set_cs_wait(0)
    await ClockCycles(dut.clk, 10)
    await _add_weight_and_verify(dut, spi, 0x10, 10)
    await spi.cmd_reset_buffer()
    await ClockCycles(dut.clk, 20)

    # cs_wait = 7 (maximum delay)
    await spi.cmd_set_cs_wait(7)
    await ClockCycles(dut.clk, 10)
    await _add_weight_and_verify(dut, spi, 0x11, 20, max_attempts=30)
    await spi.cmd_reset_buffer()
    await ClockCycles(dut.clk, 20)

    # cs_wait = 3 (back to default)
    await spi.cmd_set_cs_wait(3)
    await ClockCycles(dut.clk, 10)
    await _add_weight_and_verify(dut, spi, 0x12, 30)


@cocotb.test()
async def test_double_reset_isolation(dut):
    spi = await start_clocks(dut)

    set_ram(dut, ram_addr(0, 0x50), to_unsigned_8(100))
    await spi.cmd_add_weight(0x50)

    opcode, _, sum1 = await spi.cmd_read_poll()
    assert opcode == OP_RESP_VALID
    assert sum1 == 100

    await spi.cmd_reset_buffer()
    await ClockCycles(dut.clk, 20)

    resp = await spi.cmd_read_raw()
    opcode_after, _, _ = parse_read_response(resp)
    assert opcode_after == OP_RESP_INVALID

    set_ram(dut, ram_addr(0, 0x60), to_unsigned_8(25))
    await spi.cmd_add_weight(0x60)

    opcode2, valid2, sum2 = await spi.cmd_read_poll()
    assert opcode2 == OP_RESP_VALID
    assert valid2 == 1
    assert sum2 == 25, f"After reset+new weight, expected 25, got {sum2}"


@cocotb.test()
async def test_set_clk_div(dut):
    """Change clk_div, measure RAM SCK period, verify it doubles per step."""
    spi = await start_clocks(dut)

    # Measure SCK period at default clk_div=2 (div-by-8)
    period_div2 = await _measure_ram_sck_period(dut, spi, 0x42, 77)
    await spi.cmd_reset_buffer()
    await ClockCycles(dut.clk, 20)

    # Change to clk_div=3 (div-by-16), measure again
    await spi.cmd_set_clk_div(3)
    await ClockCycles(dut.clk, 10)
    period_div3 = await _measure_ram_sck_period(dut, spi, 0x43, 55)
    await spi.cmd_reset_buffer()
    await ClockCycles(dut.clk, 20)

    dut._log.info(f"SCK period at div=2: {period_div2}ns, div=3: {period_div3}ns")

    # div-by-16 should be ~2x the period of div-by-8
    ratio = period_div3 / period_div2
    assert 1.5 < ratio < 2.5, \
        f"Expected ~2x ratio, got {ratio:.2f} (div2={period_div2}ns, div3={period_div3}ns)"

    # Restore default
    await spi.cmd_set_clk_div(2)
    await ClockCycles(dut.clk, 10)


@cocotb.test()
async def test_set_clk_div_boundaries(dut):
    """Verify operations complete at each clk_div boundary value."""
    spi = await start_clocks(dut)

    # div=0 (div-by-2) and div=1 (div-by-4) are too fast for the RAM SPI slave:
    # the edge detector needs ≥2 sys clocks per SCK half-period.
    # div=2 (div-by-8, default) and div=3 (div-by-16) are verified here.
    for div_val, ram_val, idx in [(2, 30, 0x102), (3, 40, 0x103)]:
        await spi.cmd_set_clk_div(div_val)
        await ClockCycles(dut.clk, 20)
        await _add_weight_and_verify(dut, spi, idx, ram_val, max_attempts=40)
        await spi.cmd_reset_buffer()
        await ClockCycles(dut.clk, 80)
        dut._log.info(f"clk_div={div_val}: operation completed successfully")

    # Restore default
    await spi.cmd_set_clk_div(2)
    await ClockCycles(dut.clk, 10)
