"""
Gate-level CDC stress tests for SPI interfaces.

Exercises clock domain crossings with varied SPI speeds, random phase
offsets, and back-to-back transactions.  Designed to catch timing issues
that only appear in GLS with real gate delays.

Tests:
  - test_cdc_spi_speed_sweep:   Write+readback at multiple SPI frequencies
  - test_cdc_phase_stress:      Random phase offsets between all 3 clocks
  - test_cdc_back_to_back_cs:   Minimal chip-select gaps between frames
"""

import cocotb
import random
from cocotb.clock import Clock
from cocotb.triggers import Timer, ClockCycles
from perceptron.helpers import (
    SpiMasterDriver,
    set_ram, get_ram, ram_addr, to_signed_8, to_unsigned_8,
    parse_read_response,
    OP_RESP_VALID, OP_RESP_INVALID,
    MAX_WEIGHTS, INDEX_WIDTH,
)


async def start_clocks_with_phase(dut, sys_period_ns, ram_period_ns,
                                  spi_half_ns, sys_phase_ps=0,
                                  ram_phase_ps=0):
    """Start clocks with configurable phase offsets (in picoseconds)."""
    if sys_phase_ps:
        await Timer(sys_phase_ps, unit="ps")
    cocotb.start_soon(Clock(dut.clk, sys_period_ns, unit="ns").start())

    if ram_phase_ps:
        await Timer(ram_phase_ps, unit="ps")
    cocotb.start_soon(Clock(dut.ram_slave_clk, ram_period_ns, unit="ns").start())

    dut.rst_n.value = 0
    dut.slave_sck_ext.value = 0
    dut.slave_scs_ext.value = 1
    dut.slave_mosi_ext.value = 0

    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 30)

    return SpiMasterDriver(dut, half_period_ns=spi_half_ns)


async def seed_ram_pattern(dut, index, values):
    """Write a list of weight values into RAM slots for a given index."""
    for slot, val in enumerate(values):
        set_ram(dut, ram_addr(slot, index), to_unsigned_8(val))


async def write_read_verify(spi, dut, index, weight_val, label=""):
    """Add weight, read prediction, update, then verify RAM was written."""
    set_ram(dut, ram_addr(0, index), to_unsigned_8(weight_val))

    await spi.cmd_add_weight(index)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll(max_attempts=20)
    assert opcode == OP_RESP_VALID, \
        f"[{label}] Expected VALID, got {opcode:#x}"
    assert valid_bit == 1, f"[{label}] Valid bit should be 1"
    assert sum_signed == to_signed_8(to_unsigned_8(weight_val)), \
        f"[{label}] Expected sum {to_signed_8(to_unsigned_8(weight_val))}, got {sum_signed}"

    # Update (increment) and verify RAM write-back
    await spi.cmd_update_and_wait(sign=1, max_attempts=20)

    actual = to_signed_8(get_ram(dut, ram_addr(0, index)))
    expected = to_signed_8(to_unsigned_8(weight_val)) + 1
    assert actual == expected, \
        f"[{label}] RAM after update: expected {expected}, got {actual}"


@cocotb.test()
async def test_cdc_spi_speed_sweep(dut):
    """Write+readback at multiple SPI clock frequencies to stress synchronizers."""
    SYS_PERIOD = 20  # 50 MHz

    # SPI half-periods to sweep: from slow (safe) to fast (stresses CDC).
    # The 2-stage synchronizer + edge detection needs >= 3 system clocks
    # per SPI half-period, so min ~60ns half at 50 MHz sys clock.
    spi_half_periods = [200, 100, 80, 60]

    for spi_half in spi_half_periods:
        # Random phase offset for each speed
        ram_phase = random.randint(0, 5000)
        await Timer(ram_phase, unit="ps")

        spi = await start_clocks_with_phase(
            dut,
            sys_period_ns=SYS_PERIOD,
            ram_period_ns=10,
            spi_half_ns=spi_half,
            ram_phase_ps=random.randint(0, 5000),
        )

        spi_freq_khz = 1_000_000 / (2 * spi_half)
        label = f"spi_half={spi_half}ns ({spi_freq_khz:.0f}kHz)"
        dut._log.info(f"Testing {label}")

        index = random.randint(0, (1 << INDEX_WIDTH) - 1)
        weight = random.randint(1, 126)  # stay away from saturation

        await write_read_verify(spi, dut, index, weight, label=label)

        # Reset buffer for next iteration
        await spi.cmd_reset_buffer()
        await ClockCycles(dut.clk, 20)

        dut._log.info(f"  {label} PASS")


@cocotb.test()
async def test_cdc_phase_stress(dut):
    """Run multiple iterations with random phase offsets between all 3 clocks."""
    NUM_ITERATIONS = 5
    SYS_PERIOD = 20

    for i in range(NUM_ITERATIONS):
        sys_phase = random.randint(0, 10000)
        ram_phase = random.randint(0, 10000)
        spi_half = random.choice([80, 100, 150])

        spi = await start_clocks_with_phase(
            dut,
            sys_period_ns=SYS_PERIOD,
            ram_period_ns=10,
            spi_half_ns=spi_half,
            sys_phase_ps=sys_phase,
            ram_phase_ps=ram_phase,
        )

        label = f"iter={i} sys_phase={sys_phase}ps ram_phase={ram_phase}ps spi_half={spi_half}ns"
        dut._log.info(f"Testing {label}")

        # Load multiple weights and verify sum
        n_weights = min(3, MAX_WEIGHTS)
        index = 0x42
        weights = [random.randint(1, 40) for _ in range(n_weights)]
        for slot, w in enumerate(weights):
            set_ram(dut, ram_addr(slot, index), to_unsigned_8(w))

        for _ in range(n_weights):
            await spi.cmd_add_weight(index)

        opcode, valid_bit, sum_signed = await spi.cmd_read_poll(max_attempts=20)
        expected_sum = sum(weights)
        assert opcode == OP_RESP_VALID, f"[{label}] Expected VALID, got {opcode:#x}"
        assert sum_signed == expected_sum, \
            f"[{label}] Expected sum {expected_sum}, got {sum_signed}"

        await spi.cmd_reset_buffer()
        await ClockCycles(dut.clk, 20)

        dut._log.info(f"  {label} PASS (sum={sum_signed})")


@cocotb.test()
async def test_cdc_back_to_back_cs(dut):
    """Rapid chip-select toggling with minimal inter-frame gaps."""
    ram_phase = random.randint(0, 5000)
    spi = await start_clocks_with_phase(
        dut,
        sys_period_ns=20,
        ram_period_ns=10,
        spi_half_ns=80,
        ram_phase_ps=ram_phase,
    )

    index = 0x10
    weight = 25
    set_ram(dut, ram_addr(0, index), to_unsigned_8(weight))

    # Override half_period to use a tighter CS gap driver
    fast_spi = SpiMasterDriver(dut, half_period_ns=60)

    # Send several back-to-back add_weight with minimal gaps
    N_BURSTS = MAX_WEIGHTS
    for slot in range(N_BURSTS):
        w = 10 + slot
        set_ram(dut, ram_addr(slot, index), to_unsigned_8(w))

    for _ in range(N_BURSTS):
        await fast_spi.cmd_add_weight(index)

    opcode, valid_bit, sum_signed = await fast_spi.cmd_read_poll(max_attempts=20)

    expected = sum(10 + s for s in range(N_BURSTS))
    assert opcode == OP_RESP_VALID, f"Expected VALID, got {opcode:#x}"
    assert sum_signed == expected, f"Expected sum {expected}, got {sum_signed}"

    dut._log.info(f"Back-to-back CS: sum={sum_signed} (expected {expected}) PASS")
