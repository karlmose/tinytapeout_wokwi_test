# Cocotb testbench for ram_interface

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_ROOT = $(PWD)/../src/verilog

# RTL sources
VERILOG_SOURCES += $(VERILOG_ROOT)/src/ram_interface.v

# SPI library
VERILOG_SOURCES += $(VERILOG_ROOT)/lib/verilog_spi/spi_module.v
VERILOG_SOURCES += $(VERILOG_ROOT)/lib/verilog_spi/clock_divider.v
VERILOG_SOURCES += $(VERILOG_ROOT)/lib/verilog_spi/pos_edge_det.v
VERILOG_SOURCES += $(VERILOG_ROOT)/lib/verilog_spi/neg_edge_det.v

TOPLEVEL = ram_interface
MODULE = test_weight_spi

include $(shell cocotb-config --makefiles)/Makefile.sim
