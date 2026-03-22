// SPI command decoder

`default_nettype none
`timescale 1ns/1ps

module pred_slave_spi (
    input wire clk,
    input wire rst_n,

    input wire sck,
    input wire scs,
    input wire mosi,
    output wire miso,

    input wire [11:0] read,
    input wire read_valid,
    input wire update_done,

    output wire add_weight_cmd,
    output wire update_weight_cmd,
    output wire reset_buffer_cmd,
    output wire [8:0] index,
    output reg update_sign,

    output reg [2:0] cs_wait_cfg,
    output reg [1:0] spi_clk_div
);

    wire spi_processing;
    wire spi_start_next = 1'b1;
    wire [15:0] spi_data_recv;
    reg [15:0] spi_data_send;
    wire spi_ready;
    reg spi_reset;

    reg [1:0] sck_sync, scs_sync, mosi_sync;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sck_sync  <= 2'b00;
            scs_sync  <= 2'b11;
            mosi_sync <= 2'b00;
        end else begin
            sck_sync  <= {sck_sync[0], sck};
            scs_sync  <= {scs_sync[0], scs};
            mosi_sync <= {mosi_sync[0], mosi};
        end
    end

    wire sck_synced  = sck_sync[1];
    wire scs_synced  = scs_sync[1];
    wire mosi_synced = mosi_sync[1];

    spi_module #(
        .SPI_MASTER(1'b0),
        .SPI_WORD_LEN(16),
        .CPOL(1'b0),
        .CPHA(1'b0)
    ) spi_inst (
        .master_clock(clk),
        .SCLK_OUT(),
        .SCLK_IN(sck_synced),
        .SS_OUT(),
        .SS_IN(scs_synced),
        .OUTPUT_SIGNAL(miso),
        .processing_word(spi_processing),
        .process_next_word(spi_start_next),
        .data_word_send(spi_data_send),
        .INPUT_SIGNAL(mosi_synced),
        .data_word_recv(spi_data_recv),
        .do_reset(spi_reset),
        .is_ready(spi_ready)
    );

    reg prev_processing;

    localparam OP_ADD          = 4'b0001;
    localparam OP_UPDATE       = 4'b0010;
    localparam OP_READ         = 4'b0011;
    localparam OP_SET_CS_WAIT  = 4'b0100;
    localparam OP_RESET_BUF    = 4'b0101;
    localparam OP_SET_CLK_DIV  = 4'b0110;

    localparam RESP_VALID       = 4'b0001;
    localparam RESP_INVALID     = 4'b0010;
    localparam RESP_UPDATE_DONE = 4'b0011;

    reg word_done;
    wire [3:0] opcode = spi_data_recv[15:12];

    assign index       = spi_data_recv[8:0];

    assign add_weight_cmd    = word_done && (opcode == OP_ADD);
    assign update_weight_cmd = word_done && (opcode == OP_UPDATE);
    assign reset_buffer_cmd  = word_done && (opcode == OP_RESET_BUF);


    reg update_done_flag;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            spi_reset           <= 1'b1;
            spi_data_send       <= 16'd0;
            prev_processing     <= 1'b0;
            update_sign         <= 1'b0;
            cs_wait_cfg         <= 3'd3;
            spi_clk_div         <= 2'd2;   // div-by-8 default
            word_done           <= 1'b0;
            update_done_flag    <= 1'b0;
        end else begin
            spi_reset       <= 1'b0;
            prev_processing <= spi_processing;

            word_done <= prev_processing && !spi_processing;

            if (update_done)
                update_done_flag <= 1'b1;

            if (prev_processing && !spi_processing) begin
                case (spi_data_recv[15:12])
                    OP_ADD: begin
                        spi_data_send <= {spi_data_recv[15:12], 12'd0};
                        update_done_flag <= 1'b0;
                    end
                    OP_UPDATE: begin
                        update_sign <= spi_data_recv[0];
                        spi_data_send <= {spi_data_recv[15:12], 12'd0};
                        update_done_flag <= 1'b0;
                    end
                    OP_READ: begin
                        if (update_done_flag) begin
                            spi_data_send <= {RESP_UPDATE_DONE, 12'd0};
                            update_done_flag <= 1'b0;
                        end else if (read_valid)
                            spi_data_send <= {RESP_VALID, read};
                        else
                            spi_data_send <= {RESP_INVALID, 12'd0};
                    end
                    OP_SET_CS_WAIT: begin
                        cs_wait_cfg <= spi_data_recv[2:0];
                        spi_data_send <= {spi_data_recv[15:12], 12'd0};
                    end
                    OP_RESET_BUF: begin
                        spi_data_send <= {spi_data_recv[15:12], 12'd0};
                    end
                    OP_SET_CLK_DIV: begin
                        spi_clk_div <= spi_data_recv[1:0];
                        spi_data_send <= {spi_data_recv[15:12], 12'd0};
                    end
                    default: begin
                        spi_data_send <= 16'd0;
                    end
                endcase
            end
        end
    end

endmodule
