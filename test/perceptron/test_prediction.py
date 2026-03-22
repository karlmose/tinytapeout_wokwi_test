"""
Prediction tests for pred_top.

Tests:
  - test_prediction: Load 4 weights, verify signed sum + valid (SPI-only polling)
  - test_read_sum:   Verify OP_READ returns correct sum and valid bit
"""

import cocotb
from perceptron.helpers import (
    start_clocks, set_ram, ram_addr, to_unsigned_8,
    OP_RESP_VALID,
)


@cocotb.test()
async def test_prediction(dut):
    """Load 4 weight indices, poll until valid, verify signed sum."""
    spi = await start_clocks(dut)

    # Weights: +10, -5, +20, -30 → sum = -5
    set_ram(dut, ram_addr(0, 0x10), to_unsigned_8(10))
    set_ram(dut, ram_addr(1, 0x20), to_unsigned_8(-5))
    set_ram(dut, ram_addr(2, 0x30), to_unsigned_8(20))
    set_ram(dut, ram_addr(3, 0x40), to_unsigned_8(-30))

    for idx in [0x10, 0x20, 0x30, 0x40]:
        await spi.cmd_add_weight(idx)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    dut._log.info(f"Sum = {sum_signed}, valid = {valid_bit}")
    assert opcode == OP_RESP_VALID, f"Expected VALID response, got opcode {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"
    assert sum_signed == -5, f"Expected sum -5, got {sum_signed}"


@cocotb.test()
async def test_read_sum(dut):
    """Verify OP_READ returns correct sum and valid bit."""
    spi = await start_clocks(dut)

    set_ram(dut, ram_addr(0, 0x01), to_unsigned_8(42))

    await spi.cmd_add_weight(0x01)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    dut._log.info(f"OP_READ: opcode={opcode:#x} valid={valid_bit} sum={sum_signed}")
    assert opcode == OP_RESP_VALID, f"Expected OP_WRITE_READ_VALID, got {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"
    assert sum_signed == 42, f"Expected 42, got {sum_signed}"


@cocotb.test()
async def test_prediction_all_positive(dut):
    """4 positive weights → verify positive sum."""
    spi = await start_clocks(dut)

    weights = [10, 20, 30, 40]
    indices = [0x10, 0x20, 0x30, 0x40]
    expected_sum = sum(weights)

    for slot, (idx, w) in enumerate(zip(indices, weights)):
        set_ram(dut, ram_addr(slot, idx), to_unsigned_8(w))

    for idx in indices:
        await spi.cmd_add_weight(idx)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    assert opcode == OP_RESP_VALID, f"Expected VALID, got {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"
    assert sum_signed == expected_sum, f"Expected {expected_sum}, got {sum_signed}"
    assert sum_signed > 0, "Sum of all-positive weights must be positive"


@cocotb.test()
async def test_prediction_all_negative(dut):
    """4 negative weights → verify negative sum."""
    spi = await start_clocks(dut)

    weights = [-10, -20, -30, -40]
    indices = [0x10, 0x20, 0x30, 0x40]
    expected_sum = sum(weights)

    for slot, (idx, w) in enumerate(zip(indices, weights)):
        set_ram(dut, ram_addr(slot, idx), to_unsigned_8(w))

    for idx in indices:
        await spi.cmd_add_weight(idx)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    assert opcode == OP_RESP_VALID, f"Expected VALID, got {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"
    assert sum_signed == expected_sum, f"Expected {expected_sum}, got {sum_signed}"
    assert sum_signed < 0, "Sum of all-negative weights must be negative"


@cocotb.test()
async def test_prediction_mixed_zero_sum(dut):
    """Weights that cancel to exactly 0."""
    spi = await start_clocks(dut)

    weights = [50, -50, 25, -25]
    indices = [0x10, 0x20, 0x30, 0x40]

    for slot, (idx, w) in enumerate(zip(indices, weights)):
        set_ram(dut, ram_addr(slot, idx), to_unsigned_8(w))

    for idx in indices:
        await spi.cmd_add_weight(idx)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    assert opcode == OP_RESP_VALID, f"Expected VALID, got {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"
    assert sum_signed == 0, f"Expected zero sum, got {sum_signed}"


@cocotb.test()
async def test_single_weight_extremes(dut):
    """Single weights at +127, -128, and 0 — verify exact sum for each."""
    spi = await start_clocks(dut)

    for label, weight_val, expected in [
        ("+127", 127, 127),
        ("-128", -128, -128),
        ("0",    0,    0),
    ]:
        # Reset buffer for each sub-test
        await spi.cmd_reset_buffer()
        from cocotb.triggers import ClockCycles
        await ClockCycles(dut.clk, 20)

        set_ram(dut, ram_addr(0, 0xEE), to_unsigned_8(weight_val))
        await spi.cmd_add_weight(0xEE)

        opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

        assert opcode == OP_RESP_VALID, \
            f"[{label}] Expected VALID, got {opcode:#x}"
        assert valid_bit == 1, \
            f"[{label}] Valid bit should be 1"
        assert sum_signed == expected, \
            f"[{label}] Expected {expected}, got {sum_signed}"
        dut._log.info(f"  Extreme {label}: sum={sum_signed} ✓")
