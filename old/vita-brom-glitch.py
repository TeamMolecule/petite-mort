from __future__ import print_function, division

import time
import logging
import os
import csv

import chipwhisperer as cw
from chipwhisperer.capture.scopes.cwhardware.ChipWhispererExtra import CWExtraSettings
from chipwhisperer.capture.targets.mmccapture_readers._base import MMCPacket
from chipwhisperer.capture.targets.MMCCapture import MMCCapture as cwtarget
#from scripting_utils import GlitchResultsDisplay

VITA_CLK_FREQ = 3300000
MIN_WIDTH = 1000
MAX_WIDTH = 1000
MIN_OFFSET = 0
MAX_OFFSET = 0

logging.basicConfig(level=logging.WARN)
scope = cw.scope()
target = cw.target(scope, cwtarget)

# setup parameters needed for glitch the stm32f
scope.glitch.clk_src = 'clkgen'

scope.clock.clkgen_freq = VITA_CLK_FREQ
scope.io.tio1 = "serial_rx"
scope.io.tio2 = "serial_tx"

# setup MMC trigger to look for READ_SINGLE_BLOCK of 0x0 response
scope.advancedSettings.cwEXTRA.setTriggerModule(CWExtraSettings.MODULE_MMCTRIGGER)
mmctrigger = scope.mmcTrigger
mmctrigger.setMatchCmd(True)
mmctrigger.setCmdIndex(MMCPacket.Cmd.READ_SINGLE_BLOCK.value)
mmctrigger.setDirection(2)
mmctrigger.setDataCompareOp(1)
mmctrigger.setTriggerData('0x0')
mmctrigger.setTriggerNext(True)

# get MMC output
mmc = target.mmc

# format output table
headers = ['last read block', 'num reads', 'width', 'offset', 'success']
#glitch_display = GlitchResultsDisplay(headers)

# set glitch parameters
# trigger glitches with external trigger
scope.glitch.trigger_src = 'ext_single'

outputs = []
reads = []
widths = []
offsets = []

# glitch cycle
open('glitch_out.csv', 'w').close()
f = open('glitch_out.csv', 'ab')
writer = csv.writer(f)
target.init()
powered_on = False
for offset in xrange(MIN_OFFSET, MAX_OFFSET+1):
    # set offset from trigger
    scope.glitch.ext_offset = offset
    for width in xrange(MIN_WIDTH, MAX_WIDTH+1):
        print('trying offset {}, width {}'.format(offset, width))

        # set repeat count
        scope.glitch.repeat = width

        # flush the buffer
        while mmc.count() > 0:
            pkt = mmc.read()
            print(str(pkt))

        # reset device
        if powered_on:
            scope.io.nrst = 'low'
            scope.io.nrst = 'disabled'
        else:
            scope.io.pdid = 'low'
            time.sleep(3)
            scope.io.pdid = 'disabled'
            powered_on = True

        timeout = 500
        # wait for target to finish
        seen_read = 0
        last_read_pkt = None
        while timeout > 0:
            while mmc.count() > 0:
                pkt = mmc.read()
                print(str(pkt))
                if pkt.cmd == MMCPacket.Cmd.READ_SINGLE_BLOCK and pkt.is_req:
                    seen_read += 1
                    last_read_pkt = pkt
            timeout -= 1
            time.sleep(0.01)

        if seen_read > 0:
            output = '0x{:X}'.format(last_read_pkt.content)
        else:
            output = ''

        # read from the targets buffer
        outputs.append(output)
        reads.append(seen_read)
        widths.append(width)
        offsets.append(offset)

        # for table display purposes
        success = seen_read > 1 and last_read_pkt.content != 0x0
        data = [repr(output), seen_read, width, offset, success]
        #glitch_display.add_data(data)
        writer.writerow(data)

f.close()
# the rest of the data is available with the outputs, widths, and offsets lists
#glitch_display.display_table()
print('Done')
