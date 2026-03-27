# SPDX-FileCopyrightText: 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

"""Main test module — imports all test suites so cocotb discovers them."""

import cocotb
from perceptron.helpers import start_clocks, OP_RESP_INVALID

# Import all test modules so their @cocotb.test() functions are registered
from perceptron.test_prediction import *    # noqa: F401,F403
from perceptron.test_update import *        # noqa: F401,F403
from perceptron.test_config import *        # noqa: F401,F403
from perceptron.test_spi_edge_cases import *  # noqa: F401,F403
from perceptron.test_end_to_end import *    # noqa: F401,F403
from perceptron.test_gls_cdc import *       # noqa: F401,F403


@cocotb.test()
async def test_spi_smoke(dut):
    """Send OP_READ with no weights loaded — expect OP_RESP_INVALID."""
    spi = await start_clocks(dut)

    resp = await spi.cmd_read_raw()

    opcode = (resp >> 12) & 0xF
    dut._log.info(f"OP_READ response: {resp:#06x}, opcode={opcode:#x}")
    assert opcode == OP_RESP_INVALID, \
        f"Expected OP_RESP_INVALID ({OP_RESP_INVALID:#x}), got {opcode:#x}"
