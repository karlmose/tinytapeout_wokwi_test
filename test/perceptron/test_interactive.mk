# Interactive cocotb testbench — run with:
#   make -f test_interactive.mk SIM=icarus

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_ROOT = $(PWD)/../src/verilog

# RTL sources
VERILOG_SOURCES += $(VERILOG_ROOT)/src/pred.v
VERILOG_SOURCES += $(VERILOG_ROOT)/src/perceptron.v
VERILOG_SOURCES += $(VERILOG_ROOT)/src/ram_interface.v
VERILOG_SOURCES += $(VERILOG_ROOT)/src/pred_slave_spi.v

# SPI library
VERILOG_SOURCES += $(VERILOG_ROOT)/lib/verilog_spi/spi_module.v
VERILOG_SOURCES += $(VERILOG_ROOT)/lib/verilog_spi/clock_divider.v
VERILOG_SOURCES += $(VERILOG_ROOT)/lib/verilog_spi/pos_edge_det.v
VERILOG_SOURCES += $(VERILOG_ROOT)/lib/verilog_spi/neg_edge_det.v

# Test models
VERILOG_SOURCES += $(PWD)/models/spi_ram_slave.v

# Test wrapper
VERILOG_SOURCES += $(PWD)/tb_wrapper.v

TOPLEVEL = tb_wrapper
MODULE = test_interactive

include $(shell cocotb-config --makefiles)/Makefile.sim
