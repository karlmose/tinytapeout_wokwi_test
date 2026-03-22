`default_nettype none
`timescale 1ns/1ps

module neg_edge_det (
    input sig,
    input clk,
    output ne
);

    reg sig_dly;

    always @(posedge clk) sig_dly <= sig;

    assign ne = ~sig & sig_dly;

endmodule
