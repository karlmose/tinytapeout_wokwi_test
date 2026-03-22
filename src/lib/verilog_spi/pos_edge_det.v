`default_nettype none
`timescale 1ns/1ps

module pos_edge_det (
    input sig,
    input clk,
    output pe
);

    reg sig_dly;

    always @(posedge clk) sig_dly <= sig;

    assign pe = sig & ~sig_dly;

endmodule
