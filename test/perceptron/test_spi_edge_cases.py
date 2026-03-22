"""
SPI edge-case tests for pred_top.

Tests:
  - test_rapid_back_to_back:       Minimal inter-frame spacing
  - test_invalid_opcode:           Unknown opcode doesn't crash DUT
  - test_max_buffer_four_weights:  4 weights (max) all accumulated
  - test_buffer_overflow_fifth:    5th weight silently ignored
  - test_update_before_weights:    OP_UPDATE with empty buffer
  - test_read_before_weights:      OP_READ with no weights → INVALID
"""

import cocotb
from cocotb.triggers import ClockCycles
from perceptron.helpers import (
    start_clocks, SpiMasterDriver,
    set_ram, get_ram, ram_addr, to_signed_8, to_unsigned_8,
    parse_read_response,
    OP_RESP_VALID, OP_RESP_INVALID,
)


@cocotb.test()
async def test_rapid_back_to_back(dut):
    """Send multiple OP_ADD commands back-to-back with minimal spacing."""
    spi = await start_clocks(dut)

    # Set known weights in all 4 slots
    set_ram(dut, ram_addr(0, 0x01), to_unsigned_8(5))
    set_ram(dut, ram_addr(1, 0x01), to_unsigned_8(10))
    set_ram(dut, ram_addr(2, 0x01), to_unsigned_8(15))
    set_ram(dut, ram_addr(3, 0x01), to_unsigned_8(20))

    # Rapid-fire 4 add_weight commands (no extra delays)
    for _ in range(4):
        await spi.cmd_add_weight(0x01)

    # Poll for result
    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    assert opcode == OP_RESP_VALID, \
        f"Expected VALID, got {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"
    expected_sum = 5 + 10 + 15 + 20
    assert sum_signed == expected_sum, \
        f"Expected sum {expected_sum}, got {sum_signed}"

    dut._log.info(f"Rapid back-to-back: sum={sum_signed} (expected {expected_sum}) ✓")


@cocotb.test()
async def test_invalid_opcode(dut):
    """Send an undefined opcode (0xF), then do a normal flow — DUT must survive."""
    spi = await start_clocks(dut)

    # Send word with opcode=0xF (undefined)
    invalid_word = (0xF << 12) | 0x000
    resp = await spi.send_word(invalid_word)
    dut._log.info(f"Invalid opcode response: {resp:#06x}")

    # Now do a normal prediction — must still work
    set_ram(dut, ram_addr(0, 0x55), to_unsigned_8(42))
    await spi.cmd_add_weight(0x55)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    assert opcode == OP_RESP_VALID, \
        f"After invalid opcode, expected VALID, got {opcode:#x}"
    assert valid_bit == 1, \
        "After invalid opcode, valid bit should be 1"
    assert sum_signed == 42, \
        f"After invalid opcode, expected sum 42, got {sum_signed}"

    dut._log.info(f"Invalid opcode recovery: sum={sum_signed} ✓")


@cocotb.test()
async def test_max_buffer_four_weights(dut):
    """Add exactly 4 weights (buffer maximum), verify all contribute to sum."""
    spi = await start_clocks(dut)

    # 4 distinct weights: +1 through +4 → sum = 10
    weight_vals = [1, 2, 3, 4]
    indices = [0x10, 0x20, 0x30, 0x40]

    for slot, (idx, w) in enumerate(zip(indices, weight_vals)):
        set_ram(dut, ram_addr(slot, idx), to_unsigned_8(w))

    for idx in indices:
        await spi.cmd_add_weight(idx)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    expected_sum = sum(weight_vals)
    assert opcode == OP_RESP_VALID, \
        f"Expected VALID, got {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"
    assert sum_signed == expected_sum, \
        f"Expected sum {expected_sum} with 4 weights, got {sum_signed}"

    dut._log.info(f"4-weight buffer: sum={sum_signed} (expected {expected_sum}) ✓")


@cocotb.test()
async def test_buffer_overflow_fifth(dut):
    """Add 5 weights — 5th should be silently ignored (buffer is 4 deep)."""
    spi = await start_clocks(dut)

    # 5 weights: +1 through +5
    weight_vals = [1, 2, 3, 4, 5]
    indices = [0x10, 0x20, 0x30, 0x40, 0x50]

    for slot, (idx, w) in enumerate(zip(indices, weight_vals)):
        set_ram(dut, ram_addr(slot % 4, idx), to_unsigned_8(w))

    for idx in indices:
        await spi.cmd_add_weight(idx)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    # Only first 4 should contribute: sum = 1+2+3+4 = 10
    expected_sum = sum(weight_vals[:4])
    assert opcode == OP_RESP_VALID, \
        f"Expected VALID, got {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"
    assert sum_signed == expected_sum, \
        f"Expected sum {expected_sum} (5th ignored), got {sum_signed}"

    dut._log.info(f"Buffer overflow: sum={sum_signed} (expected {expected_sum}, 5th ignored) ✓")


@cocotb.test()
async def test_update_before_weights(dut):
    """Send OP_UPDATE with no weights loaded — ignored, DUT stays responsive."""
    spi = await start_clocks(dut)

    # Send update with empty buffer — perceptron.v guards with no_in_buffer > 0,
    # so it stays in STATE_PREDICT and the update is silently ignored.
    await spi.cmd_update(sign=1)
    await ClockCycles(dut.clk, 50)

    # Normal prediction flow should work without needing a reset_buffer
    set_ram(dut, ram_addr(0, 0x99), to_unsigned_8(33))
    await spi.cmd_add_weight(0x99)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    assert opcode == OP_RESP_VALID, \
        f"After empty update, expected VALID, got {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"
    assert sum_signed == 33, \
        f"After empty update, expected sum 33, got {sum_signed}"

    dut._log.info(f"Update-before-weights ignored: sum={sum_signed}")


@cocotb.test()
async def test_read_before_weights(dut):
    """OP_READ immediately after reset with no weights → INVALID."""
    spi = await start_clocks(dut)

    # Immediately read — no weights loaded
    resp = await spi.cmd_read_raw()
    opcode, valid_bit, sum_signed = parse_read_response(resp)

    assert opcode == OP_RESP_INVALID, \
        f"Expected INVALID ({OP_RESP_INVALID:#x}) with no weights, got {opcode:#x}"
    assert valid_bit == 0, \
        f"Valid bit should be 0 with no weights, got {valid_bit}"

    dut._log.info(f"Read-before-weights: opcode={opcode:#x} (INVALID) ✓")
