"""
SPI edge-case tests for pred_top.

Tests:
  - test_rapid_back_to_back:       Minimal inter-frame spacing
  - test_invalid_opcode:           Unknown opcode doesn't crash DUT
  - test_max_buffer_weights:       MAX_WEIGHTS all accumulated
  - test_buffer_overflow:          (MAX_WEIGHTS+1)th weight silently ignored
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
    MAX_WEIGHTS,
)


@cocotb.test()
async def test_rapid_back_to_back(dut):
    """Send multiple OP_ADD commands back-to-back with minimal spacing."""
    spi = await start_clocks(dut)

    # Set known weights in all MAX_WEIGHTS slots
    weight_vals = list(range(5, 5 * (MAX_WEIGHTS + 1), 5))  # 5, 10, 15, ...
    for slot in range(MAX_WEIGHTS):
        set_ram(dut, ram_addr(slot, 0x01), to_unsigned_8(weight_vals[slot]))

    # Rapid-fire add_weight commands (no extra delays)
    for _ in range(MAX_WEIGHTS):
        await spi.cmd_add_weight(0x01)

    # Poll for result
    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    assert opcode == OP_RESP_VALID, \
        f"Expected VALID, got {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"
    expected_sum = sum(weight_vals)
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
async def test_max_buffer_weights(dut):
    """Add exactly MAX_WEIGHTS weights (buffer maximum), verify all contribute."""
    spi = await start_clocks(dut)

    weight_vals = list(range(1, MAX_WEIGHTS + 1))
    indices = [0x10 * (i + 1) for i in range(MAX_WEIGHTS)]

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
        f"Expected sum {expected_sum} with {MAX_WEIGHTS} weights, got {sum_signed}"

    dut._log.info(f"{MAX_WEIGHTS}-weight buffer: sum={sum_signed} (expected {expected_sum}) ✓")


@cocotb.test()
async def test_buffer_overflow(dut):
    """Add MAX_WEIGHTS+1 weights — last should be silently ignored."""
    spi = await start_clocks(dut)

    n = MAX_WEIGHTS + 1
    weight_vals = list(range(1, n + 1))
    indices = [0x10 * (i + 1) for i in range(n)]

    for slot, (idx, w) in enumerate(zip(indices, weight_vals)):
        set_ram(dut, ram_addr(slot % MAX_WEIGHTS, idx), to_unsigned_8(w))

    for idx in indices:
        await spi.cmd_add_weight(idx)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    expected_sum = sum(weight_vals[:MAX_WEIGHTS])
    assert opcode == OP_RESP_VALID, \
        f"Expected VALID, got {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"
    assert sum_signed == expected_sum, \
        f"Expected sum {expected_sum} (overflow ignored), got {sum_signed}"

    dut._log.info(f"Buffer overflow: sum={sum_signed} (expected {expected_sum}, extra ignored) ✓")


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
