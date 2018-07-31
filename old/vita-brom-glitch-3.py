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
    UNEXPECTED_PACKET = 3,
    READ_ENP = 4,
    RESTARTED_IMMEDIATELY = 5,
    RESTARTED_DELAYED = 6,
    RECOVERED_READ = 7


VITA_CLK_FREQ = 3300000
MIN_OFFSET = 151200
MAX_OFFSET = 151500
MIN_WIDTH = 1
MAX_WIDTH = 1
VITA_UART0_BAUD = 115200
TIME_RESET_HOLD = 0

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
open('glitch_out_2.csv', 'w').close()
f = open('glitch_out_2.csv', 'ab')
writer = csv.writer(f)
target.init()
for offset in xrange(MIN_OFFSET, MAX_OFFSET+1):
    # set offset from trigger
    scope.glitch.ext_offset = offset
    for width in xrange(MIN_WIDTH, MAX_WIDTH+1):
        print('trying offset {}, width {}'.format(offset, width))

        # reset device
        scope.io.nrst = 'low'
        scope.glitch.repeat = width
        # flush the buffer
        time.sleep(TIME_RESET_HOLD)
        while mmc.count() > 0:
            pkt = mmc.read()
            #if pkt.cmd == MMCPacket.Cmd.READ_SINGLE_BLOCK and pkt.is_req:
            #    print(str(pkt))
        scope.io.nrst = 'disabled'

        timeout = 100
        # wait for target to finish
        state = States.STARTUP
        unexpected_count = 0
        while timeout > 0:
            while mmc.count() > 0:
                pkt = mmc.read()
                print(str(pkt))
                if pkt.is_req:
                    if state == States.STARTUP:
                        if pkt.cmd == MMCPacket.Cmd.READ_SINGLE_BLOCK and pkt.content == 0x0:
                            state = States.READ_MBR
                    elif state == States.READ_MBR:
                        if pkt.cmd == MMCPacket.Cmd.SEND_STATUS and pkt.content == 0x10000:
                            state = States.READ_MBR_STATUS
                        elif pkt.cmd == MMCPacket.Cmd.GO_IDLE_STATE and pkt.content == 0x0:
                            state = States.RESTARTED_IMMEDIATELY
                        else:
                            state = States.UNEXPECTED_PACKET
                    elif state == States.READ_MBR_STATUS:
                        if pkt.cmd == MMCPacket.Cmd.READ_SINGLE_BLOCK and pkt.content == 0x8000:
                            state = States.READ_ENP
                        elif pkt.cmd == MMCPacket.Cmd.GO_IDLE_STATE and pkt.content == 0x0:
                            state = States.RESTARTED_IMMEDIATELY
                        else:
                            state = States.UNEXPECTED_PACKET
                    elif state == States.UNEXPECTED_PACKET:
                        if unexpected_count < 2:
                            if pkt.cmd == MMCPacket.Cmd.READ_SINGLE_BLOCK and pkt.content == 0x8001:
                                state = States.RECOVERED_READ
                            elif pkt.cmd == MMCPacket.Cmd.GO_IDLE_STATE and pkt.content == 0x0:
                                state = States.RESTARTED_DELAYED
                            else:
                                unexpected_count += 1
                #if state.value >= States.READ_ENP.value:
                #    timeout = 0
                #    break
            else:
                time.sleep(0.1)
                timeout -= 1

        # for table display purposes
        data = [offset, width, state]
        print(data)
        #glitch_display.add_data(data)
        writer.writerow(data)
        f.flush()

f.close()
# the rest of the data is available with the outputs, widths, and offsets lists
#glitch_display.display_table()
print('Done')
