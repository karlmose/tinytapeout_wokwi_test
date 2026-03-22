// Main perceptron logic, prediction, updating, etc

`default_nettype none
`timescale 1ns/1ps

module perceptron #(
    parameter ADDR_WIDTH  = 9,
    parameter MAX_WEIGHTS = 4
) (
    input wire clk,
    input wire rst_n,

    input wire [ADDR_WIDTH-1:0] weight_addr,
    input wire add_weight,
    input wire reset_buffer,
    input wire update,
    input wire update_sign,

    output wire valid,
    output reg signed [10:0] sum,
    output wire update_done,

    output wire [ADDR_WIDTH+$clog2(MAX_WEIGHTS)-1:0] ram_addr,
    output wire ram_start_read,
    output wire ram_inc,
    output wire ram_dec,
    input wire signed [7:0] ram_weight,
    input wire ram_read_valid,
    input wire ram_write_done,
    input wire ram_busy
);

    localparam STATE_PREDICT = 1'b0;
    localparam STATE_UPDATE  = 1'b1;
    localparam SLOT_WIDTH    = $clog2(MAX_WEIGHTS);
    localparam CNT_WIDTH     = $clog2(MAX_WEIGHTS) + 1; // needs to hold 0..MAX_WEIGHTS


    reg [MAX_WEIGHTS*ADDR_WIDTH-1:0] index_buffer;
    reg [CNT_WIDTH-1:0] weight_count;
    reg [CNT_WIDTH-1:0] processed_count;
    reg state;
    reg ram_read_valid_prev;
    reg ram_write_done_prev;
    reg write_data_ready;

    assign valid = (state == STATE_PREDICT) && weight_count > 0 &&
                   processed_count == weight_count;


    wire read_done_rising  = ram_read_valid && !ram_read_valid_prev;
    wire write_done_rising = ram_write_done && !ram_write_done_prev;
    wire is_last_weight    = (processed_count + 1'b1 == weight_count);
    assign update_done = (state == STATE_UPDATE) && write_done_rising && is_last_weight;

    assign ram_addr = {processed_count[SLOT_WIDTH-1:0], index_buffer[processed_count * ADDR_WIDTH +: ADDR_WIDTH]};

    assign ram_start_read = (!ram_busy && processed_count < weight_count) &&
                            ((state == STATE_PREDICT) ||
                             (state == STATE_UPDATE && !write_data_ready));

    wire do_write = (state == STATE_UPDATE && processed_count < weight_count &&
                     write_data_ready && !ram_write_done && !ram_busy);
    assign ram_inc = do_write && update_sign;
    assign ram_dec = do_write && !update_sign;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state                <= STATE_PREDICT;
            ram_read_valid_prev  <= 1'b0;
            ram_write_done_prev  <= 1'b0;
            write_data_ready     <= 1'b0;
            sum              <= 11'd0;
            index_buffer         <= {(MAX_WEIGHTS*ADDR_WIDTH){1'b0}};
            weight_count         <= {CNT_WIDTH{1'b0}};
            processed_count      <= {CNT_WIDTH{1'b0}};
        end else begin
            ram_read_valid_prev <= ram_read_valid;
            ram_write_done_prev <= ram_write_done;

            if (reset_buffer) begin
                state           <= STATE_PREDICT;
                weight_count    <= {CNT_WIDTH{1'b0}};
                processed_count <= {CNT_WIDTH{1'b0}};
                sum         <= 11'd0;
                write_data_ready <= 1'b0;
            end else begin
                case (state)
                    STATE_PREDICT: begin
                        if (processed_count < weight_count) begin
                            if (read_done_rising) begin
                                sum <= sum + ram_weight;
                                processed_count <= processed_count + 1'b1;
                            end
                        end

                        if (add_weight && weight_count < MAX_WEIGHTS[CNT_WIDTH-1:0]) begin
                            index_buffer[weight_count * ADDR_WIDTH +: ADDR_WIDTH] <= weight_addr;
                            weight_count <= weight_count + 1'b1;
                        end

                        if (update && weight_count > 0 && processed_count == weight_count) begin
                            processed_count <= {CNT_WIDTH{1'b0}};
                            state <= STATE_UPDATE;
                        end
                    end

                    STATE_UPDATE: begin
                        if (read_done_rising)
                            write_data_ready <= 1'b1;

                        if (processed_count < weight_count) begin
                            if (write_done_rising) begin
                                if (is_last_weight) begin
                                    state            <= STATE_PREDICT;
                                    weight_count     <= {CNT_WIDTH{1'b0}};
                                    processed_count  <= {CNT_WIDTH{1'b0}};
                                    sum          <= 11'd0;
                                    write_data_ready <= 1'b0;
                                end else begin
                                    processed_count  <= processed_count + 1'b1;
                                    write_data_ready <= 1'b0;
                                end
                            end
                        end
                    end
                endcase
            end
        end
    end

endmodule
