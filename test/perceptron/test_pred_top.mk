# Cocotb testbench for pred_top — runs all test modules
# Tests the full system: pred_slave_spi + perceptron + ram_interface + spi_ram_slave

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_ROOT = $(CURDIR)/../../src

# RTL sources
VERILOG_SOURCES += $(VERILOG_ROOT)/project.v
VERILOG_SOURCES += $(VERILOG_ROOT)/perceptron.v
VERILOG_SOURCES += $(VERILOG_ROOT)/ram_interface.v
VERILOG_SOURCES += $(VERILOG_ROOT)/pred_slave_spi.v

# SPI library
VERILOG_SOURCES += $(VERILOG_ROOT)/lib/verilog_spi/spi_module.v
VERILOG_SOURCES += $(VERILOG_ROOT)/lib/verilog_spi/clock_divider.v
VERILOG_SOURCES += $(VERILOG_ROOT)/lib/verilog_spi/pos_edge_det.v
VERILOG_SOURCES += $(VERILOG_ROOT)/lib/verilog_spi/neg_edge_det.v

# Test models
VERILOG_SOURCES += $(CURDIR)/models/spi_ram_slave.v

# Test wrapper
VERILOG_SOURCES += $(CURDIR)/tb_wrapper.v

TOPLEVEL = tb_wrapper

# MODULE lists all test files (cocotb runs them all)
MODULE = test_prediction,test_update,test_config,test_end_to_end,test_spi_edge_cases

include $(shell cocotb-config --makefiles)/Makefile.sim
