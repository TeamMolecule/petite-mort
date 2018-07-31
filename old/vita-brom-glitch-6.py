from __future__ import print_function, division

import time
import logging
import os
import csv
from enum import IntEnum

import chipwhisperer as cw
from chipwhisperer.capture.scopes.cwhardware.ChipWhispererExtra import CWExtraSettings
from chipwhisperer.capture.targets.mmccapture_readers._base import MMCPacket
from chipwhisperer.capture.targets.MMCCapture import MMCCapture as cwtarget
from chipwhisperer.common.utils import pluginmanager
from chipwhisperer.capture.targets.simpleserial_readers.cwlite import SimpleSerial_ChipWhispererLite
#from scripting_utils import GlitchResultsDisplay

class States(IntEnum):
    STARTUP = 0,
    READ_MBR = 1,
    READ_MBR_STATUS = 2,
    UNEXPECTED_READ = 3,
    UNEXPECTED_PACKET = 4,
    SUCCESS = 5,
    RESTARTED_AFTER_READ = 6,
    RESTARTED_AFTER_STATUS = 7

CW_SYSCLK_FREQ = 96000000
VITA_CLK_FREQ = 12000000
MIN_OFFSET = 39865
MAX_OFFSET = 50000
MIN_WIDTH = 40
MAX_WIDTH = 70
VITA_UART0_BAUD = 115200
TIME_RESET_HOLD = 0
OFFSET_STEP = 1
WIDTH_STEP = 5
FAST_MODE = 1

logging.basicConfig(level=logging.WARN)
scope = cw.scope()
target = cw.target(scope, cwtarget)

# setup parameters needed for glitch the stm32f
scope.glitch.clk_src = 'clkgen'

scope.clock.clkgen_freq = VITA_CLK_FREQ
scope.io.tio1 = "serial_rx"
scope.io.tio2 = "serial_tx"

# setup MMC trigger to look for READ_SINGLE_BLOCK of 0x0 response

mmctrigger = scope.mmcTrigger
mmctrigger.setMatchCmd(True)
mmctrigger.setCmdIndex(MMCPacket.Cmd.READ_SINGLE_BLOCK.value)
mmctrigger.setDirection(2)
mmctrigger.setDataCompareOp(1)
mmctrigger.setTriggerData('0x0')
mmctrigger.setTriggerNext(True)

# get MMC output
mmc = target.mmc

# get serial console
ser_cons = pluginmanager.getPluginsInDictFromPackage("chipwhisperer.capture.targets.simpleserial_readers", True, False)
ser = ser_cons[SimpleSerial_ChipWhispererLite._name]
ser.con(scope)
ser.setBaud(VITA_UART0_BAUD)

# format output table
headers = ['num packets', 'width', 'offset', 'success']
#glitch_display = GlitchResultsDisplay(headers)

# set glitch parameters
# trigger glitches with external trigger
scope.glitch.trigger_src = 'ext_continuous'
scope.glitch.output = 'enable_only'
scope.io.hs2 = 'clkgen'

# enable trigger
scope.advancedSettings.cwEXTRA.setTriggerModule(CWExtraSettings.MODULE_MMCTRIGGER)
scope.advancedSettings.cwEXTRA.setTargetGlitchOut('A', True)

# glitch cycle
open('glitch_out_6.csv', 'w').close()
f = open('glitch_out_6.csv', 'ab')
writer = csv.writer(f)
target.init()
for offset in xrange(MIN_OFFSET, MAX_OFFSET+1, OFFSET_STEP):
    # set offset from trigger
    scope.glitch.ext_offset = offset
    for width in xrange(MIN_WIDTH, MAX_WIDTH+1, WIDTH_STEP):
        print('trying offset {}, width {}'.format(offset, width))

        # reset device
        scope.io.nrst = 'low'
        scope.glitch.repeat = width
        #scope.glitch.repeat = 1
        # flush the buffer
        time.sleep(TIME_RESET_HOLD)

        timeout = 10
        # wait for target to finish
        state = States.STARTUP

        last_cnt = 0
        while mmc.count() > 0:
            pkt = mmc.read()
            last_cnt = pkt.num
            print(str(pkt))

        scope.io.nrst = 'disabled'
        timestamp = 0
        restarted = 0
        while timeout > 0:
            while mmc.count() > 0:
                timeout = 10
                pkt = mmc.read()
                if pkt.num < last_cnt:
                    timestamp = ((pkt.num + 0x10000 - last_cnt) * 0x100 * 1000.0) / CW_SYSCLK_FREQ
                else:
                    timestamp = ((pkt.num - last_cnt) * 0x100 * 1000.0) / CW_SYSCLK_FREQ
                last_cnt = pkt.num
                print('[{:10.5f}ms] {}'.format(timestamp, str(pkt)))
                if pkt.is_req:
                    if pkt.cmd == MMCPacket.Cmd.GO_IDLE_STATE:
                        restarted += 1
                    if state == States.STARTUP:
                        if pkt.cmd == MMCPacket.Cmd.READ_SINGLE_BLOCK and pkt.content == 0x0:
                            state = States.READ_MBR
                    elif state == States.READ_MBR:
                        if pkt.cmd == MMCPacket.Cmd.SEND_STATUS:
                            state = States.READ_MBR_STATUS
                        elif pkt.cmd == MMCPacket.Cmd.GO_IDLE_STATE:
                            state = States.RESTARTED_AFTER_READ
                        elif pkt.cmd == MMCPacket.Cmd.READ_SINGLE_BLOCK:
                            state = States.UNEXPECTED_READ
                        else:
                            state = States.UNEXPECTED_PACKET
                    elif state == States.READ_MBR_STATUS:
                        if pkt.cmd == MMCPacket.Cmd.GO_IDLE_STATE:
                            state = States.RESTARTED_AFTER_STATUS
                        elif pkt.cmd == MMCPacket.Cmd.READ_SINGLE_BLOCK:
                            if pkt.content == 0x8000:
                                state = States.SUCCESS
                            else:
                                state = States.UNEXPECTED_READ
                        else:
                            state = States.UNEXPECTED_PACKET
                if restarted > 2 or FAST_MODE and state.value > States.RESTARTED_AFTER_READ.value:
                    timeout = -1
                    break
            else:
                time.sleep(0.1)
                timeout -= 1

        # for table display purposes
        data = [offset, width, state, timestamp]
        print(data)
        #glitch_display.add_data(data)
        writer.writerow(data)
        f.flush()

f.close()
# the rest of the data is available with the outputs, widths, and offsets lists
#glitch_display.display_table()
print('Done')
