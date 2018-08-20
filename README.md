# Petite Mort

These are a set of ChipWhisperer scripts for glitching bootrom on Vita.

## Usage

Copy the scripts to `scripting-examples` in your ChipWhisperer installation. 
Then open a shell in that directory and run the script manually.

## Parameters

In each script, there are a number of constants you can change to tune the 
glitching. They are currently set to known working parameters.

| Name                | Description                                                                             |
|---------------------|-----------------------------------------------------------------------------------------|
| CW_SYSCLK_FREQ      | CW system clock frequency. You shouldn't change this unless you know what you're doing. |
| VITA_CLK_FREQ       | Vita clock input, CW extclkgen output frequency.                                        |
| VITA_UART0_BAUD     | UART baud rate, this should change when VITA_CLK_FREQ changes.                          |
| MIN_OFFSET          | Starting offset from trigger in units of extclkgen cycles.                              |
| MAX_OFFSET          | Upper bound offset from trigger in units of extclkgen cycles.                           |
| OFFSET_STEP         | Offset stride in units of extclkgen cycles for search.                                  |
| MIN_WIDTH           | Starting width of glitch in units of extclkgen cycles.                                  |
| MAX_WIDTH           | Upper bound width of glitch in units of extclkgen cycles.                               |
| WIDTH_STEP          | Width stride in units of extclkgen cycles for search.                                   |
| POWER_ON_HOLD       | Number of seconds to hold power button on reset in seconds. (N/A to all script)         |
| GLITCH_FIND_TIMEOUT | Timeout in 1/10 seconds of MMC traffic idle                                             |
| PAYLOAD_TIMEOUT     | Timeout in 1/10 seconds of UART idle (after glitch successful)                          |
| VERBOSE             | Verbose logging                                                                         |

## Scripts

### Size Check Overflow

Usage: `python2 vita-petite-mort.py [output.bin]` where output.bin is an 
optional file to dump serial output to.

This script requires an MBR with offset 0x30 pointing to 0x8000 and 
offset 0x34 having a value > 0xE1. Your payload should have `jmp` instructions 
past offset 0x1c000 (in bytes) to your code and be flashed to block 0x8000 
for 0x100 blocks.

### Exception Handler

Usage: `python2 vita-petite-mort-exception.py [output.bin]` where output.bin 
is an optional file to dump serial output to.

This script requires an MBR with offset 0x30 pointing to your payload at block 
0x8000 and offset 0x34 having a value <= 0xE1 (to pass size check). You should 
fill the first 0x20 bytes of the payload with `jmp` instructions to your code.

### tzpwn

Usage: `python2 vita-petite-mort-tzpwn.py [output.bin]` where output.bin 
is an optional file to dump serial output to.

This script requires tzpwn installed and auto-booted into with ensō. tzpwn 
will call secure_kernel.enp loading which copies in 0x40 bytes and overwrite 
the exception vectors. This script will then try to cause an exception.

### Deux

Usage: `python2 vita-petite-mort-deux.py`

This script performs a double-glitch. First on reset and then on the size 
check overflow (see above for requirements). `P1_` and `P2_` parameters 
determines the settings for each glitch.

### Exception Deux

Usage: `python2 vita-petite-mort-exception-deux.py`

Same as Deux but using the exception handler method.

### Manual

Usage: `vita-petite-mort-manual.py [output.bin]` where output.bin 
is an optional file to dump serial output to.

Not tested working. This script waits for second_loader to finish and then 
manually trigger a number of glitches. Do not use this, use the tzpwn version 
instead.
