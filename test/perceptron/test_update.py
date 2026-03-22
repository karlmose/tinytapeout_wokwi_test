"""
Update and saturation tests for pred_top.

Tests:
  - test_update_increment: Predict → increment → verify RAM (SPI-only)
  - test_saturation_positive: +127 stays at +127
  - test_saturation_negative: -128 stays at -128
"""

import cocotb
from perceptron.helpers import (
    start_clocks,
    set_ram, get_ram, ram_addr, to_signed_8, to_unsigned_8,
    MAX_WEIGHTS,
)


@cocotb.test()
async def test_update_increment(dut):
    """Load weights, predict, update (increment), verify RAM contents."""
    spi = await start_clocks(dut)

    set_ram(dut, ram_addr(0, 0x10), to_unsigned_8(10))
    set_ram(dut, ram_addr(1, 0x20), to_unsigned_8(-5))

    await spi.cmd_add_weight(0x10)
    await spi.cmd_add_weight(0x20)

    await spi.cmd_read_poll()       # wait for prediction ready
    await spi.cmd_update_and_wait(sign=1)  # increment + wait for done

    val0 = get_ram(dut, ram_addr(0, 0x10))
    val1 = get_ram(dut, ram_addr(1, 0x20))

    dut._log.info(f"Weight 0: {to_signed_8(val0)} (expected 11)")
    dut._log.info(f"Weight 1: {to_signed_8(val1)} (expected -4)")
    assert to_signed_8(val0) == 11, f"Expected 11, got {to_signed_8(val0)}"
    assert to_signed_8(val1) == -4, f"Expected -4, got {to_signed_8(val1)}"


@cocotb.test()
async def test_saturation_positive(dut):
    """Verify +127 stays at +127 after increment."""
    spi = await start_clocks(dut)

    set_ram(dut, ram_addr(0, 0xAA), to_unsigned_8(127))

    await spi.cmd_add_weight(0xAA)
    await spi.cmd_read_poll()
    await spi.cmd_update_and_wait(sign=1)

    val = get_ram(dut, ram_addr(0, 0xAA))
    dut._log.info(f"Saturated +127 after inc: {to_signed_8(val)}")
    assert to_signed_8(val) == 127, f"Expected 127, got {to_signed_8(val)}"


@cocotb.test()
async def test_saturation_negative(dut):
    """Verify −128 stays at −128 after decrement."""
    spi = await start_clocks(dut)

    set_ram(dut, ram_addr(0, 0xBB), to_unsigned_8(-128))

    await spi.cmd_add_weight(0xBB)
    await spi.cmd_read_poll()
    await spi.cmd_update_and_wait(sign=0)

    val = get_ram(dut, ram_addr(0, 0xBB))
    dut._log.info(f"Saturated -128 after dec: {to_signed_8(val)}")
    assert to_signed_8(val) == -128, f"Expected -128, got {to_signed_8(val)}"


@cocotb.test()
async def test_update_decrement(dut):
    """Load weights, predict, decrement, verify each RAM cell decreased by 1."""
    spi = await start_clocks(dut)

    set_ram(dut, ram_addr(0, 0x10), to_unsigned_8(10))
    set_ram(dut, ram_addr(1, 0x20), to_unsigned_8(-5))

    await spi.cmd_add_weight(0x10)
    await spi.cmd_add_weight(0x20)

    opcode, valid_bit, _ = await spi.cmd_read_poll()
    assert opcode == 0x1, f"Expected VALID, got {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"

    await spi.cmd_update_and_wait(sign=0)  # decrement

    val0 = get_ram(dut, ram_addr(0, 0x10))
    val1 = get_ram(dut, ram_addr(1, 0x20))

    dut._log.info(f"Weight 0: {to_signed_8(val0)} (expected 9)")
    dut._log.info(f"Weight 1: {to_signed_8(val1)} (expected -6)")
    assert to_signed_8(val0) == 9, f"Expected 9, got {to_signed_8(val0)}"
    assert to_signed_8(val1) == -6, f"Expected -6, got {to_signed_8(val1)}"


@cocotb.test()
async def test_update_all_weights(dut):
    """Load MAX_WEIGHTS weights, increment, verify all RAM cells updated."""
    spi = await start_clocks(dut)

    # Alternate positive/negative, staying well within [-128, 127]
    initial = [10 * ((-1) ** i) * (i + 1) for i in range(MAX_WEIGHTS)]
    indices = [0x10 * (i + 1) for i in range(MAX_WEIGHTS)]

    for slot, (idx, w) in enumerate(zip(indices, initial)):
        set_ram(dut, ram_addr(slot, idx), to_unsigned_8(w))

    for idx in indices:
        await spi.cmd_add_weight(idx)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()
    assert opcode == 0x1, f"Expected VALID, got {opcode:#x}"
    assert valid_bit == 1, "Valid bit should be 1"
    expected_sum = sum(initial)
    assert sum_signed == expected_sum, f"Expected sum {expected_sum}, got {sum_signed}"

    await spi.cmd_update_and_wait(sign=1)  # increment

    expected_after = [w + 1 for w in initial]
    for slot, (idx, exp) in enumerate(zip(indices, expected_after)):
        val = get_ram(dut, ram_addr(slot, idx))
        actual = to_signed_8(val)
        dut._log.info(f"Weight {slot}: {actual} (expected {exp})")
        assert actual == exp, f"Weight {slot}: expected {exp}, got {actual}"


@cocotb.test()
async def test_double_saturation_positive(dut):
    """Set weight=126, inc twice → 127 after first, still 127 after second."""
    spi = await start_clocks(dut)

    set_ram(dut, ram_addr(0, 0xCC), to_unsigned_8(126))

    # First increment: 126 → 127
    await spi.cmd_add_weight(0xCC)
    await spi.cmd_read_poll()
    await spi.cmd_update_and_wait(sign=1)

    val = get_ram(dut, ram_addr(0, 0xCC))
    assert to_signed_8(val) == 127, f"After 1st inc, expected 127, got {to_signed_8(val)}"

    # Second increment: 127 → 127 (saturated)
    await spi.cmd_add_weight(0xCC)
    await spi.cmd_read_poll()
    await spi.cmd_update_and_wait(sign=1)

    val = get_ram(dut, ram_addr(0, 0xCC))
    assert to_signed_8(val) == 127, f"After 2nd inc, expected 127, got {to_signed_8(val)}"

    dut._log.info("Double saturation +127 ✓")


@cocotb.test()
async def test_double_saturation_negative(dut):
    """Set weight=-127, dec twice → -128 after first, still -128 after second."""
    spi = await start_clocks(dut)

    set_ram(dut, ram_addr(0, 0xDD), to_unsigned_8(-127))

    # First decrement: -127 → -128
    await spi.cmd_add_weight(0xDD)
    await spi.cmd_read_poll()
    await spi.cmd_update_and_wait(sign=0)

    val = get_ram(dut, ram_addr(0, 0xDD))
    assert to_signed_8(val) == -128, f"After 1st dec, expected -128, got {to_signed_8(val)}"

    # Second decrement: -128 → -128 (saturated)
    await spi.cmd_add_weight(0xDD)
    await spi.cmd_read_poll()
    await spi.cmd_update_and_wait(sign=0)

    val = get_ram(dut, ram_addr(0, 0xDD))
    assert to_signed_8(val) == -128, f"After 2nd dec, expected -128, got {to_signed_8(val)}"

    dut._log.info("Double saturation -128 ✓")


@cocotb.test()
async def test_write_then_read_roundtrip(dut):
    """Write via SPI update, then read the updated weight back via prediction."""
    spi = await start_clocks(dut)

    # Start with weight = 0 at index 0xAA
    set_ram(dut, ram_addr(0, 0xAA), to_unsigned_8(0))

    # Predict + increment: 0 → 1
    await spi.cmd_add_weight(0xAA)
    await spi.cmd_read_poll()
    await spi.cmd_update_and_wait(sign=1)

    val = get_ram(dut, ram_addr(0, 0xAA))
    assert to_signed_8(val) == 1, f"After inc, expected 1, got {to_signed_8(val)}"

    # Now read the same weight back via a new prediction — sum should be 1
    await spi.cmd_add_weight(0xAA)
    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()

    assert opcode == 0x1, f"Expected VALID, got {opcode:#x}"
    assert valid_bit == 1
    assert sum_signed == 1, f"Expected sum 1 after roundtrip, got {sum_signed}"


@cocotb.test()
async def test_multi_cycle_predict_update(dut):
    """Three consecutive predict-update cycles on the same weight."""
    spi = await start_clocks(dut)

    set_ram(dut, ram_addr(0, 0x77), to_unsigned_8(10))

    # Cycle 1: predict (sum=10), increment → 11
    await spi.cmd_add_weight(0x77)
    opcode, _, sum1 = await spi.cmd_read_poll()
    assert opcode == 0x1 and sum1 == 10
    await spi.cmd_update_and_wait(sign=1)

    # Cycle 2: predict (sum=11), decrement → 10
    await spi.cmd_add_weight(0x77)
    opcode, _, sum2 = await spi.cmd_read_poll()
    assert opcode == 0x1 and sum2 == 11, f"Cycle 2: expected 11, got {sum2}"
    await spi.cmd_update_and_wait(sign=0)

    # Cycle 3: predict (sum=10), increment → 11
    await spi.cmd_add_weight(0x77)
    opcode, _, sum3 = await spi.cmd_read_poll()
    assert opcode == 0x1 and sum3 == 10, f"Cycle 3: expected 10, got {sum3}"
    await spi.cmd_update_and_wait(sign=1)

    val = get_ram(dut, ram_addr(0, 0x77))
    assert to_signed_8(val) == 11, f"Final weight expected 11, got {to_signed_8(val)}"
