"""End-to-end trace-driven branch prediction test with 3 clock domains."""

import os
import cocotb
from cocotb.triggers import Timer, ClockCycles
import random
from perceptron.helpers import start_clocks, OP_RESP_VALID

TRACE_PATH = os.path.join(os.path.dirname(__file__), "data", "trace.txt")
MAX_BRANCHES = 100


def load_trace(path, limit=MAX_BRANCHES):
    trace = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            pc = int(parts[0], 16)
            outcome = int(parts[1])
            trace.append((pc, outcome))
            if len(trace) >= limit:
                break
    return trace


@cocotb.test()
async def test_end_to_end_3clk(dut):
    """Run trace-driven learning with 3 realistic clock domains, SPI-only."""
    SYS_PERIOD_NS = 10       # 100 MHz sim clock
    RAM_PERIOD_NS = 83.33    # 12 MHz (external RAM)
    SPI_HALF_NS   = 250      # ~2 MHz controller

    ram_phase_ps = random.randint(0, 5000)
    await Timer(ram_phase_ps, unit="ps")

    spi = await start_clocks(
        dut,
        sys_period_ns=SYS_PERIOD_NS,
        ram_period_ns=RAM_PERIOD_NS,
        spi_half_ns=SPI_HALF_NS,
    )

    dut._log.info(f"Clocks: sys={SYS_PERIOD_NS}ns, "
                  f"ram={RAM_PERIOD_NS}ns (12MHz), "
                  f"spi_half={SPI_HALF_NS}ns (~2MHz)")

    for i in range(8192):
        dut.ram_slave.memory[i].value = 0

    trace = load_trace(TRACE_PATH, limit=MAX_BRANCHES)
    dut._log.info(f"Loaded {len(trace)} branches from trace.txt")

    history = 0
    errors = 0
    total = 0

    for pc, outcome in trace:
        total += 1

        idx0 = (pc ^ (pc >> 8)) & 0x3FF
        idx1 = (pc ^ (pc >> 4)) & 0x3FF
        idx2 = (pc ^ history) & 0x3FF
        idx3 = (pc ^ (history >> 4)) & 0x3FF

        for idx in [idx0, idx1, idx2, idx3]:
            await spi.cmd_add_weight(idx)

        opcode, valid_bit, sum_signed = await spi.cmd_read_poll()
        assert opcode == OP_RESP_VALID, \
            f"[{total}] Expected VALID ({OP_RESP_VALID:#x}), got {opcode:#x}"
        assert valid_bit == 1, f"[{total}] Valid bit should be 1"

        predicted_taken = (sum_signed >= 0)
        actual_taken = (outcome == 1)

        if total <= 20 or total % 20 == 0:
            dut._log.info(f"[{total:3d}] PC={pc:#010x} sum={sum_signed:+4d} "
                          f"pred={'T' if predicted_taken else 'N'} "
                          f"actual={'T' if actual_taken else 'N'}")

        if predicted_taken != actual_taken:
            errors += 1
            sign = 1 if actual_taken else 0
            await spi.cmd_update_and_wait(sign)
        else:
            await spi.cmd_reset_buffer()
            await ClockCycles(dut.clk, 30)

        history = ((history << 1) | outcome) & 0xFFFFFFFF

    accuracy = (1 - errors / total) * 100
    dut._log.info(f"Done: {total} branches, {errors} mispredictions ({accuracy:.1f}% accuracy)")
    assert total == len(trace), f"Expected {len(trace)} branches, processed {total}"
