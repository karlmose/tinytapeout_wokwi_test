`default_nettype none

module tt_um_tinyperceptron_karlmose (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

  wire _unused = &{ena, 1'b0, ui_in[7:4], uio_in[7:3], uio_in[1:0]};

  wire slave_sck_ext    = ui_in[0];
  wire slave_scs_ext    = ui_in[1];
  wire slave_mosi_ext   = ui_in[2];
  wire ram_spi_miso_ext = uio_in[2];

  wire slave_miso;
  wire ram_spi_cs;
  wire ram_spi_sck;
  wire ram_spi_mosi;

  assign uio_out = {4'b0000, ram_spi_sck, 1'b0, ram_spi_mosi, ram_spi_cs};
  assign uio_oe  = 8'b0000_1011;
  assign uo_out  = {7'b0000000, slave_miso};

  reg [1:0] ram_miso_sync;
  always @(posedge clk or negedge rst_n) begin
      if (!rst_n) ram_miso_sync <= 2'b0;
      else        ram_miso_sync <= {ram_miso_sync[0], ram_spi_miso_ext};
  end
  wire ram_miso_synced = ram_miso_sync[1];

  localparam INDEX_WIDTH  = 9;
  localparam MAX_WEIGHTS  = 6;
  localparam RAM_ADDR_WIDTH = INDEX_WIDTH + $clog2(MAX_WEIGHTS);

  wire        cmd_add_weight;
  wire        cmd_update;
  wire        cmd_reset_buf;
  wire [8:0]  cmd_index;
  wire        cmd_update_sign;
  wire [2:0]  cfg_cs_wait_cfg;
  wire [1:0]  cfg_spi_clk_div;

  wire [RAM_ADDR_WIDTH-1:0] ram_addr;
  wire        ram_start_read;
  wire        ram_inc;
  wire        ram_dec;
  wire [7:0]  ram_weight;
  wire        ram_read_valid;
  wire        ram_write_done;
  wire        ram_busy;

  wire [10:0] perc_sum;
  wire        perc_valid;
  wire        perc_update_done;

  pred_slave_spi slave (
      .clk(clk),
      .rst_n(rst_n),
      .sck(slave_sck_ext),
      .scs(slave_scs_ext),
      .mosi(slave_mosi_ext),
      .miso(slave_miso),
      .read({perc_valid, perc_sum}),
      .read_valid(perc_valid),
      .update_done(perc_update_done),
      .add_weight_cmd(cmd_add_weight),
      .update_weight_cmd(cmd_update),
      .reset_buffer_cmd(cmd_reset_buf),
      .index(cmd_index),
      .update_sign(cmd_update_sign),
      .cs_wait_cfg(cfg_cs_wait_cfg),
      .spi_clk_div(cfg_spi_clk_div)
  );

  perceptron #(.ADDR_WIDTH(INDEX_WIDTH), .MAX_WEIGHTS(MAX_WEIGHTS)) perc (
      .clk(clk),
      .rst_n(rst_n),
      .weight_addr(cmd_index),
      .add_weight(cmd_add_weight),
      .reset_buffer(cmd_reset_buf),
      .update(cmd_update),
      .update_sign(cmd_update_sign),
      .valid(perc_valid),
      .sum(perc_sum),
      .update_done(perc_update_done),
      .ram_addr(ram_addr),
      .ram_start_read(ram_start_read),
      .ram_inc(ram_inc),
      .ram_dec(ram_dec),
      .ram_weight(ram_weight),
      .ram_read_valid(ram_read_valid),
      .ram_write_done(ram_write_done),
      .ram_busy(ram_busy)
  );

  ram_interface #(.ADDR_WIDTH(RAM_ADDR_WIDTH)) ram_if (
      .clk(clk),
      .rst_n(rst_n),
      .cs_wait_cycles(cfg_cs_wait_cfg),
      .spi_clk_div(cfg_spi_clk_div),
      .addr(ram_addr),
      .start_read(ram_start_read),
      .inc(ram_inc),
      .dec(ram_dec),
      .weight(ram_weight),
      .read_valid(ram_read_valid),
      .write_done(ram_write_done),
      .busy(ram_busy),
      .spi_cs(ram_spi_cs),
      .spi_sck(ram_spi_sck),
      .spi_mosi(ram_spi_mosi),
      .spi_miso(ram_miso_synced)
  );

endmodule
