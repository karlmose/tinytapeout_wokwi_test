// Testbench wrapper: TT module + spi_ram_slave with independent clock domains

`default_nettype none
`timescale 1ns/1ps

module tb_wrapper (
    input wire clk,
    input wire rst_n,
    input wire slave_sck_ext,
    input wire slave_scs_ext,
    input wire slave_mosi_ext,
    output wire slave_miso,
    input wire ram_slave_clk
);

    wire [7:0] uo_out;
    wire [7:0] uio_out;
    wire [7:0] uio_oe;

    wire ram_spi_cs  = uio_out[0];
    wire ram_spi_mosi = uio_out[1];
    wire ram_spi_sck = uio_out[3];
    wire ram_spi_miso;

    assign slave_miso = uo_out[0];

    tt_um_tinyperceptron_karlmose dut (
        .ui_in  ({4'b0000, 1'b0, slave_mosi_ext, slave_scs_ext, slave_sck_ext}),
        .uo_out (uo_out),
        .uio_in ({5'b00000, ram_spi_miso, 2'b00}),
        .uio_out(uio_out),
        .uio_oe (uio_oe),
        .ena    (1'b1),
        .clk    (clk),
        .rst_n  (rst_n)
    );

    spi_ram_slave ram_slave (
        .clk(ram_slave_clk),
        .rst_n(rst_n),
        .sck(ram_spi_sck),
        .scs(ram_spi_cs),
        .mosi(ram_spi_mosi),
        .miso(ram_spi_miso)
    );

endmodule
