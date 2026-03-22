// SPI master interface to SPI RAM

`default_nettype none
`timescale 1ns/1ps

module ram_interface #(
    parameter ADDR_WIDTH = 11
) (
    input wire clk,
    input wire rst_n,

    input wire [2:0] cs_wait_cycles,
    input wire [1:0] spi_clk_div,    // 0=div2, 1=div4, 2=div8 (default), 3=div16

    input wire [ADDR_WIDTH-1:0] addr,  // must be stable during transfer
    input wire start_read,
    input wire inc,
    input wire dec,

    output wire [7:0] weight,
    output reg read_valid,
    output reg write_done,
    output wire busy,

    output wire spi_cs,
    output wire spi_sck,
    output wire spi_mosi,
    input wire spi_miso
);

    reg [5:0] wait_counter;

    wire sclk_divided;
    wire spi_processing;
    reg spi_start;
    wire [31:0] spi_rx_data;
    wire spi_ready;
    reg [7:0] write_byte;

    assign weight = spi_rx_data[7:0];

    localparam STATE_IDLE      = 2'd0;
    localparam STATE_START_SPI = 2'd1;
    localparam STATE_WAIT_SPI  = 2'd2;

    reg [1:0] state;
    reg is_write;

    assign busy = (state != STATE_IDLE) || (wait_counter != 0);

    reg [3:0] clk_div_counter;
    reg clk_div_reset;

    always @(posedge clk) begin
        if (clk_div_reset) clk_div_counter <= 4'd0;
        else               clk_div_counter <= clk_div_counter + 4'd1;
    end

    assign sclk_divided = clk_div_counter[spi_clk_div];

    reg spi_reset;

    spi_module #(
        .SPI_MASTER(1'b1),
        .SPI_WORD_LEN(32),
        .CPOL(1'b0),
        .CPHA(1'b0)
    ) spi_inst (
        .master_clock(clk),
        .SCLK_OUT(spi_sck),
        .SCLK_IN(sclk_divided),
        .SS_OUT(spi_cs),
        .SS_IN(1'b1),
        .OUTPUT_SIGNAL(spi_mosi),
        .processing_word(spi_processing),
        .process_next_word(spi_start),
        .data_word_send(spi_tx_data),
        .INPUT_SIGNAL(spi_miso),
        .data_word_recv(spi_rx_data),
        .do_reset(spi_reset),
        .is_ready(spi_ready)
    );

    wire [15:0] full_addr = {{(16-ADDR_WIDTH){1'b0}}, addr};
    wire [31:0] spi_tx_data = {7'b0000_001, ~is_write, full_addr,
                               is_write ? write_byte : 8'h00};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state         <= STATE_IDLE;
            wait_counter  <= 6'd0;
            spi_start     <= 1'b0;
            write_byte    <= 8'd0;
            is_write      <= 1'b0;
            read_valid    <= 1'b0;
            write_done    <= 1'b0;
            spi_reset     <= 1'b1;
            clk_div_reset <= 1'b1;
        end else begin
            spi_reset     <= 1'b0;
            clk_div_reset <= 1'b0;

            if (!spi_cs)
                wait_counter <= {cs_wait_cycles, 3'b000};
            else if (wait_counter > 0)
                wait_counter <= wait_counter - 1'b1;

            case (state)
                STATE_IDLE: begin
                    spi_start  <= 1'b0;

                    if (wait_counter == 0 && spi_ready && !spi_processing) begin
                        if (start_read) begin
                            is_write    <= 1'b0;
                            read_valid  <= 1'b0;
                            write_done  <= 1'b0;
                            spi_start   <= 1'b1;
                            state       <= STATE_START_SPI;
                        end else if ((inc || dec) && read_valid) begin
                            is_write    <= 1'b1;
                            read_valid  <= 1'b0;
                            write_done  <= 1'b0;
                            write_byte  <=
                                (inc && !dec && weight != 8'h7F) ? weight + 8'd1 :
                                (dec && !inc && weight != 8'h80) ? weight - 8'd1 :
                                weight;
                            spi_start   <= 1'b1;
                            state       <= STATE_START_SPI;
                        end
                    end
                end

                STATE_START_SPI: begin
                    if (spi_processing) begin
                        spi_start <= 1'b0;
                        state     <= STATE_WAIT_SPI;
                    end
                end

                STATE_WAIT_SPI: begin
                    if (!spi_processing) begin
                        if (is_write) begin
                            write_done <= 1'b1;
                        end else begin
                            read_valid <= 1'b1;
                        end
                        state <= STATE_IDLE;
                    end
                end
            endcase
        end
    end

endmodule
