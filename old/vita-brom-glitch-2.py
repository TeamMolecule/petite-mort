from __future__ import print_function, division

import time
import logging
import os
import csv

import chipwhisperer as cw
from chipwhisperer.capture.scopes.cwhardware.ChipWhispererExtra import CWExtraSettings
from chipwhisperer.capture.targets.mmccapture_readers._base import MMCPacket
from chipwhisperer.capture.targets.MMCCapture import MMCCapture as cwtarget
from chipwhisperer.common.utils import pluginmanager
from chipwhisperer.capture.targets.simpleserial_readers.cwlite import SimpleSerial_ChipWhispererLite
#from scripting_utils import GlitchResultsDisplay

VITA_CLK_FREQ = 3300000
MIN_WIDTH = 20
MAX_WIDTH = 30
MIN_OFFSET = 420
MAX_OFFSET = 1000
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

packets = []
widths = []
offsets = []
seen_data = 0

# glitch cycle
open('glitch_out.csv', 'w').close()
f = open('glitch_out.csv', 'ab')
writer = csv.writer(f)
target.init()
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
        scope.io.nrst = 'low'
        scope.io.nrst = 'disabled'
        time.sleep(TIME_RESET_HOLD)

        # power on
        scope.io.pdid = 'low'
        while mmc.count() == 0:
            pass
        scope.io.pdid = 'disabled'

        timeout = 100
        # wait for target to finish
        seen_mmc = 0
        last_seen = 0
        seen_data = 0
        while timeout > 0 and not seen_data:
            while mmc.count() > 0:
                pkt = mmc.read()
                print(str(pkt))
                if pkt.cmd == MMCPacket.Cmd.READ_SINGLE_BLOCK and pkt.is_req and pkt.content != 0x0 and (pkt.content < 0x8000 or pkt.content > 0x80DD):
                    seen_data = 1
                if pkt.cmd == MMCPacket.Cmd.READ_SINGLE_BLOCK and pkt.is_req:
                    seen_mmc += 1
                last_seen = 1
            while ser.inWaiting() > 0:
                dat = ser.read()
                print(':'.join(y.encode('hex') for y in dat))
                seen_data = 1
            if not last_seen:
                timeout -= 1
                time.sleep(0.1)
            last_seen = 0

        if seen_mmc > 230:
            seen_data = 1
        #if seen_data:
        #    break

        # read from the targets buffer
        packets.append(seen_mmc)
        widths.append(width)
        offsets.append(offset)

        # for table display purposes
        success = seen_data
        data = [seen_mmc, width, offset, success]
        #glitch_display.add_data(data)
        writer.writerow(data)
        f.flush()
    else:
        continue
    break

f.close()
# the rest of the data is available with the outputs, widths, and offsets lists
#glitch_display.display_table()
print('Done')

if seen_data:
    while ser.inWaiting() > 0:
        dat = ser.read()
        print(':'.join(y.encode('hex') for y in dat))
