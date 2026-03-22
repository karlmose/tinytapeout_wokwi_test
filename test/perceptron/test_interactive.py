"""
Interactive cocotb test — prompts the user for SPI opcodes via the terminal.

Run standalone:
    make -f test_interactive.mk SIM=icarus

Menu loop:
  1. OP_ADD         — asks for 10-bit index
  2. OP_UPDATE      — asks for sign (1=inc, 0=dec)
  3. OP_READ        — sends read, prints opcode + payload
  4. OP_SET_CS_WAIT — asks for 8-bit value
  5. OP_RESET_BUF   — resets the buffer
  q. Quit
"""

import cocotb
from cocotb.triggers import ClockCycles
from perceptron.helpers import (
    start_clocks, parse_read_response,
    OP_ADD, OP_UPDATE, OP_READ, OP_SET_CS_WAIT, OP_RESET_BUF, OP_SET_CLK_DIV,
    OP_RESP_VALID, OP_RESP_INVALID, OP_RESP_UPDATE_DONE,
)

OPCODE_NAMES = {
    OP_RESP_VALID:       "RESP_VALID",
    OP_RESP_INVALID:     "RESP_INVALID",
    OP_RESP_UPDATE_DONE: "RESP_UPDATE_DONE",
}

MENU = """
╔═══════════════════════════════╗
║   SPI Interactive Console     ║
╠═══════════════════════════════╣
║  1 — OP_ADD (add weight)      ║
║  2 — OP_UPDATE (inc/dec)      ║
║  3 — OP_READ  (poll result)   ║
║  4 — OP_SET_CS_WAIT           ║
║  5 — OP_RESET_BUF             ║
║  6 — OP_SET_CLK_DIV           ║
║  q — Quit                     ║
╚═══════════════════════════════╝
"""


def _resp_str(opcode):
    return OPCODE_NAMES.get(opcode, f"UNKNOWN({opcode:#x})")


@cocotb.test()
async def test_interactive(dut):
    """Interactive SPI session driven from stdin."""

    spi = await start_clocks(dut)
    dut._log.info("Interactive mode ready — waiting for commands.")

    tx_count = 0

    while True:
        print(MENU)
        choice = input("Select opcode > ").strip().lower()

        if choice == "q":
            print(f"\n✈  Exiting after {tx_count} transactions.\n")
            break

        # ── OP_ADD ────────────────────────────────────────────────────
        if choice == "1":
            raw = input("  Enter 10-bit index (hex or decimal) > ").strip()
            try:
                index = int(raw, 0)  # auto-detect hex (0x…) or decimal
            except ValueError:
                print(f"  ✗ Invalid index: {raw}")
                continue
            index &= 0x3FF

            word = (OP_ADD << 12) | index
            resp = await spi.send_word(word)
            tx_count += 1

            print(f"  → Sent OP_ADD  index={index:#05x}")
            print(f"  ← Response raw={resp:#06x}")

        # ── OP_UPDATE ─────────────────────────────────────────────────
        elif choice == "2":
            raw = input("  Sign (1=increment, 0=decrement) > ").strip()
            try:
                sign = int(raw)
            except ValueError:
                print(f"  ✗ Invalid sign: {raw}")
                continue
            sign &= 1

            word = (OP_UPDATE << 12) | sign
            resp = await spi.send_word(word)
            tx_count += 1

            print(f"  → Sent OP_UPDATE  sign={sign}")
            print(f"  ← Response raw={resp:#06x}")

        # ── OP_READ ───────────────────────────────────────────────────
        elif choice == "3":
            # First word: send OP_READ command
            await spi.send_word(OP_READ << 12)
            # Second word: dummy to clock out response
            resp = await spi.send_word(0x0000)
            tx_count += 2

            opcode, valid_bit, sum_signed = parse_read_response(resp)

            print(f"  → Sent OP_READ + dummy")
            print(f"  ← Response raw={resp:#06x}")
            print(f"     opcode  = {_resp_str(opcode)}")
            print(f"     valid   = {valid_bit}")
            print(f"     sum     = {sum_signed:+d}")

        # ── OP_SET_CS_WAIT ────────────────────────────────────────────
        elif choice == "4":
            raw = input("  CS wait cycles (0–255) > ").strip()
            try:
                val = int(raw, 0)
            except ValueError:
                print(f"  ✗ Invalid value: {raw}")
                continue
            val &= 0xFF

            word = (OP_SET_CS_WAIT << 12) | val
            resp = await spi.send_word(word)
            tx_count += 1

            print(f"  → Sent OP_SET_CS_WAIT  val={val}")
            print(f"  ← Response raw={resp:#06x}")

        # ── OP_RESET_BUF ─────────────────────────────────────────────
        elif choice == "5":
            word = OP_RESET_BUF << 12
            resp = await spi.send_word(word)
            tx_count += 1

            print(f"  → Sent OP_RESET_BUF")
            print(f"  ← Response raw={resp:#06x}")

            await ClockCycles(dut.clk, 20)
            print(f"     (waited 20 sysclk cycles for reset to settle)")

        # ── OP_SET_CLK_DIV ──────────────────────────────────────────
        elif choice == "6":
            raw = input("  Clock div bit-select (0=/2, 1=/4, 2=/8, 3=/16) > ").strip()
            try:
                val = int(raw, 0)
            except ValueError:
                print(f"  ✗ Invalid value: {raw}")
                continue
            val &= 0x3

            word = (OP_SET_CLK_DIV << 12) | val
            resp = await spi.send_word(word)
            tx_count += 1

            print(f"  → Sent OP_SET_CLK_DIV  val={val} (div-by-{2**(val+1)})")
            print(f"  ← Response raw={resp:#06x}")

        else:
            print(f"  ✗ Unknown choice: '{choice}'")
