import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, ClockCycles

OP_ADD         = 0x1
OP_UPDATE      = 0x2
OP_READ        = 0x3
OP_SET_CS_WAIT = 0x4
OP_RESET_BUF   = 0x5
OP_SET_CLK_DIV = 0x6

OP_RESP_VALID       = 0x1
OP_RESP_INVALID     = 0x2
OP_RESP_UPDATE_DONE = 0x3

# Must match project.v localparams
INDEX_WIDTH  = 9
MAX_WEIGHTS  = 4
SLOT_WIDTH   = (MAX_WEIGHTS - 1).bit_length()  # $clog2(MAX_WEIGHTS)
RAM_ADDR_WIDTH = INDEX_WIDTH + SLOT_WIDTH


class SpiMasterDriver:

    def __init__(self, dut, half_period_ns=200):
        self.dut = dut
        self.half_period = half_period_ns

    async def send_word(self, word_16bit):
        dut = self.dut
        received = 0

        dut.slave_scs_ext.value = 0
        await Timer(self.half_period * 2, unit="ns")

        for i in range(15, -1, -1):
            bit = (word_16bit >> i) & 1
            dut.slave_mosi_ext.value = bit

            await Timer(self.half_period, unit="ns")
            dut.slave_sck_ext.value = 1
            await Timer(1, unit="ns")
            received |= (int(dut.slave_miso.value) & 1) << i

            await Timer(self.half_period - 1, unit="ns")
            dut.slave_sck_ext.value = 0

        await Timer(self.half_period * 2, unit="ns")
        dut.slave_scs_ext.value = 1
        await Timer(self.half_period * 4, unit="ns")

        return received

    async def cmd_add_weight(self, index):
        word = (OP_ADD << 12) | (index & ((1 << INDEX_WIDTH) - 1))
        await self.send_word(word)

    async def cmd_update(self, sign):
        word = (OP_UPDATE << 12) | (sign & 1)
        await self.send_word(word)

    async def cmd_read_raw(self):
        await self.send_word(OP_READ << 12)
        return await self.send_word(0x0000)

    async def cmd_read_poll(self, max_attempts=10):
        for attempt in range(1, max_attempts + 1):
            resp = await self.cmd_read_raw()
            opcode, valid_bit, sum_signed = parse_read_response(resp)
            if opcode == OP_RESP_VALID:
                return opcode, valid_bit, sum_signed
            if opcode == OP_RESP_UPDATE_DONE:
                raise AssertionError(
                    f"Got OP_RESP_UPDATE_DONE while polling for VALID (attempt {attempt})")
        raise AssertionError(
            f"OP_READ did not return VALID after {max_attempts} attempts")

    async def cmd_update_and_wait(self, sign, max_attempts=10):
        await self.cmd_update(sign)
        for attempt in range(1, max_attempts + 1):
            resp = await self.cmd_read_raw()
            opcode = (resp >> 12) & 0xF
            if opcode == OP_RESP_UPDATE_DONE:
                return resp
        raise AssertionError(
            f"OP_READ did not return UPDATE_DONE after {max_attempts} attempts")

    async def cmd_set_cs_wait(self, val_8bit):
        word = (OP_SET_CS_WAIT << 12) | (val_8bit & 0xFF)
        await self.send_word(word)

    async def cmd_reset_buffer(self):
        await self.send_word(OP_RESET_BUF << 12)

    async def cmd_set_clk_div(self, val_2bit):
        """val=0: div2, 1: div4, 2: div8 (default), 3: div16."""
        word = (OP_SET_CLK_DIV << 12) | (val_2bit & 0x3)
        await self.send_word(word)

async def start_clocks(dut, sys_period_ns=10, ram_period_ns=10, spi_half_ns=200):
    cocotb.start_soon(Clock(dut.clk, sys_period_ns, unit="ns").start())
    cocotb.start_soon(Clock(dut.ram_slave_clk, ram_period_ns, unit="ns").start())

    dut.rst_n.value = 0
    dut.slave_sck_ext.value = 0
    dut.slave_scs_ext.value = 1
    dut.slave_mosi_ext.value = 0

    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 30)

    return SpiMasterDriver(dut, half_period_ns=spi_half_ns)


def parse_read_response(resp):
    """[15:12] opcode | [11] valid | [10:0] sum (11-bit two's complement)"""
    opcode = (resp >> 12) & 0xF
    payload = resp & 0xFFF
    valid_bit = (payload >> 11) & 1
    sum_raw = payload & 0x7FF
    sum_signed = sum_raw - 2048 if sum_raw >= 1024 else sum_raw
    return opcode, valid_bit, sum_signed


def to_signed_8(val):
    return val - 256 if val >= 128 else val

def to_unsigned_8(val):
    return val & 0xFF

def ram_addr(slot, index):
    """Hardware address: {slot[SLOT_WIDTH-1:0], index[INDEX_WIDTH-1:0]}."""
    return ((slot & ((1 << SLOT_WIDTH) - 1)) << INDEX_WIDTH) | (index & ((1 << INDEX_WIDTH) - 1))

def set_ram(dut, addr_16, value_8):
    dut.ram_slave.memory[addr_16].value = value_8

def get_ram(dut, addr_16):
    return int(dut.ram_slave.memory[addr_16].value)


def assert_sum_in_range(sum_val, lo, hi, msg=""):
    assert lo <= sum_val <= hi, \
        f"Sum {sum_val} not in [{lo}, {hi}]{': ' + msg if msg else ''}"


async def predict_update_verify(spi, dut, indices, ram_slots, sign, expected_vals,
                                label=""):
    for idx in indices:
        await spi.cmd_add_weight(idx)

    opcode, valid_bit, sum_signed = await spi.cmd_read_poll()
    assert opcode == OP_RESP_VALID, \
        f"[{label}] Expected VALID opcode, got {opcode:#x}"
    assert valid_bit == 1, f"[{label}] Valid bit should be 1"

    await spi.cmd_update_and_wait(sign)

    for (slot, index), expected in zip(ram_slots, expected_vals):
        addr = ram_addr(slot, index)
        actual = to_signed_8(get_ram(dut, addr))
        assert actual == expected, \
            f"[{label}] RAM[{slot},{index:#x}] expected {expected}, got {actual}"
