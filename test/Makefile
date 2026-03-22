# Makefile
# See https://docs.cocotb.org/en/stable/quickstart.html for more info

# defaults
SIM ?= icarus
FST ?= -fst # Use more efficient FST format
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../src
PROJECT_SOURCES = project.v \
    perceptron.v \
    pred_slave_spi.v \
    ram_interface.v \
    lib/verilog_spi/spi_module.v \
    lib/verilog_spi/clock_divider.v \
    lib/verilog_spi/neg_edge_det.v \
    lib/verilog_spi/pos_edge_det.v

ifneq ($(GATES),yes)

# RTL simulation:
SIM_BUILD				= sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))
VERILOG_SOURCES += $(PWD)/perceptron/tb_wrapper.v $(PWD)/perceptron/models/spi_ram_slave.v
TOPLEVEL = tb_wrapper
COCOTB_TEST_MODULES = test

else

# Gate level simulation:
SIM_BUILD				= sim_build/gl
COMPILE_ARGS    += -DGL_TEST
COMPILE_ARGS    += -DFUNCTIONAL
COMPILE_ARGS    += -DSIM
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_io/verilog/sg13g2_io.v
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/sg13g2_stdcell.v

# this gets copied in by the GDS action workflow
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v
VERILOG_SOURCES += $(PWD)/perceptron/models/spi_ram_slave.v
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,lib/verilog_spi/spi_module.v lib/verilog_spi/clock_divider.v lib/verilog_spi/neg_edge_det.v lib/verilog_spi/pos_edge_det.v)
VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL = tb
COCOTB_TEST_MODULES = test

endif

# Allow sharing configuration between design and testbench via `include`:
COMPILE_ARGS 		+= -I$(SRC_DIR)

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim
