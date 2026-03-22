// Behavioral SPI RAM slave model — 64KB, supports READ (0x03) and WRITE (0x02)

module spi_ram_slave #(
    parameter ADDR_WIDTH = 16,
    parameter DATA_WIDTH = 8
)(
    input wire clk,
    input wire rst_n,
    input wire sck,
    input wire scs,
    input wire mosi,
    output wire miso
);

    reg [7:0] memory [0:65535];

    reg [7:0] cmd;
    reg [15:0] addr;

    wire spi_processing;
    reg [7:0] spi_data_send;
    wire [7:0] spi_data_recv;
    reg spi_reset;

    localparam CMD_READ  = 8'h03;
    localparam CMD_WRITE = 8'h02;

    integer i;
    initial begin
        for (i = 0; i < 65536; i = i + 1)
            memory[i] = 8'h00;
        memory[16'h1000] = 8'h42;
    end

    wire spi_start_next;
    assign spi_start_next = 1'b1;

    spi_module #(
        .SPI_MASTER(1'b0),
        .SPI_WORD_LEN(8),
        .CPOL(1'b0),
        .CPHA(1'b0)
    ) spi_slave_inst (
        .master_clock(clk),
        .SCLK_OUT(),
        .SCLK_IN(sck),
        .SS_OUT(),
        .SS_IN(scs),
        .OUTPUT_SIGNAL(miso),
        .processing_word(spi_processing),
        .process_next_word(spi_start_next),
        .data_word_send(spi_data_send),
        .INPUT_SIGNAL(mosi),
        .data_word_recv(spi_data_recv),
        .do_reset(spi_reset)
    );

    reg [2:0] byte_cnt;
    reg prev_processing;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            byte_cnt        <= 0;
            spi_reset       <= 1'b1;
            spi_data_send   <= 8'h00;
            prev_processing <= 0;
            cmd             <= 0;
            addr            <= 0;
        end else begin
            spi_reset       <= 0;
            prev_processing <= spi_processing;

            if (prev_processing && !spi_processing) begin
                case (byte_cnt)
                    0: cmd <= spi_data_recv;
                    1: addr[15:8] <= spi_data_recv;
                    2: addr[7:0] <= spi_data_recv;
                    3: if (cmd == CMD_WRITE) memory[addr] <= spi_data_recv;
                endcase
            end

            if (scs) begin
                byte_cnt <= 0;
                spi_data_send <= 8'h00;
            end else if (prev_processing && !spi_processing) begin
                byte_cnt <= byte_cnt + 1;
                if (byte_cnt == 2 && cmd == CMD_READ)
                    spi_data_send <= memory[{addr[15:8], spi_data_recv}];
                else
                    spi_data_send <= 8'h00;
            end
        end
    end

endmodule
