`default_nettype none
`timescale 1ns/1ps

module tb ();

  initial begin
    $dumpfile("tb.fst");
    $dumpvars(0, tb);
    #1;
  end

  reg clk;
  reg rst_n;
  wire ena;
  reg [7:0] ui_in;
  reg [7:0] uio_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;

  // Signals matching tb_wrapper interface for cocotb tests
  reg slave_sck_ext;
  reg slave_scs_ext;
  reg slave_mosi_ext;
  wire slave_miso;
  reg ram_slave_clk;

  // Map external SPI signals into ui_in
  // ui_in[0] = slave_sck_ext, ui_in[1] = slave_scs_ext,
  // ui_in[2] = slave_mosi_ext, rest = 0
  always @(*) begin
    ui_in = {4'b0000, 1'b0, slave_mosi_ext, slave_scs_ext, slave_sck_ext};
  end

  assign slave_miso = uo_out[0];

  // RAM SPI signals from uio_out
  wire ram_spi_cs   = uio_out[0];
  wire ram_spi_mosi = uio_out[1];
  wire ram_spi_sck  = uio_out[3];
  wire ram_spi_miso;

  always @(*) begin
    uio_in = {5'b00000, ram_spi_miso, 2'b00};
  end

  assign ena = 1'b1;

  tt_um_tinyperceptron_karlmose user_project (
    .ui_in  (ui_in),
    .uo_out (uo_out),
    .uio_in (uio_in),
    .uio_out(uio_out),
    .uio_oe (uio_oe),
    .ena    (ena),
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
