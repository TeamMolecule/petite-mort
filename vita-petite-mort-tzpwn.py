#!/usr/bin/env python2
## 
## vita-petite-mort-tzpwn.py -- run brom payloads
##
## Copyright (C) 2016 Yifan Lu
##
## This software may be modified and distributed under the terms
## of the MIT license.  See the LICENSE file for details.
## 
from __future__ import print_function, division

import time
import logging
import os
import csv
from enum import IntEnum

import chipwhisperer as cw
import sys
from chipwhisperer.capture.scopes.cwhardware.ChipWhispererExtra import CWExtraSettings
from chipwhisperer.capture.targets.mmccapture_readers._base import MMCPacket
from chipwhisperer.capture.targets.MMCCapture import MMCCapture as cwtarget
from chipwhisperer.common.utils import pluginmanager
from chipwhisperer.capture.targets.simpleserial_readers.cwlite import SimpleSerial_ChipWhispererLite

# Params

CW_SYSCLK_FREQ = 96000000
VITA_CLK_FREQ = 12000000
MIN_OFFSET = 4321
MAX_OFFSET = 4321
MIN_WIDTH = 100
MAX_WIDTH = 100
VITA_UART0_BAUD = 28985
OFFSET_STEP = 1
WIDTH_STEP = 5
GLITCH_FIND_TIMEOUT = 100
PAYLOAD_TIMEOUT = 1000
VERBOSE = 1
POWER_ON_HOLD = 2

# From https://gist.github.com/sbz/1080258
def hexdump(src, offset, length=16):
    FILTER = ''.join([(len(repr(chr(x))) == 3) and chr(x) or '.' for x in range(256)])
    lines = []
    for c in xrange(0, len(src), length):
        chars = src[c:c+length]
        hex = ' '.join(["%02x" % ord(x) for x in chars])
        printable = ''.join(["%s" % ((ord(x) <= 127 and FILTER[ord(x)]) or '.') for x in chars])
        lines.append("%08x  %-*s  %s\n" % (offset + c, length*3, hex, printable))
    return ''.join(lines)

logging.basicConfig(level=logging.WARN)
scope = cw.scope()
target = cw.target(scope, cwtarget)

# setup parameters needed for glitch the stm32f
scope.glitch.clk_src = 'clkgen'

scope.clock.clkgen_freq = VITA_CLK_FREQ
scope.io.tio1 = "serial_tx"
scope.io.tio2 = "serial_rx"

# setup UART trigger

scope.advancedSettings.cwEXTRA.triggermux.triggers = "tio2"
scope.decodeIO.set_decodetype(1) # USART
scope.decodeIO.set_rxbaud(VITA_UART0_BAUD)
scope.decodeIO.set_triggerpattern(list('lete\r\n'))

# get MMC output
mmc = target.mmc

# get serial console
ser_cons = pluginmanager.getPluginsInDictFromPackage("chipwhisperer.capture.targets.simpleserial_readers", True, False)
ser = ser_cons[SimpleSerial_ChipWhispererLite._name]
ser.con(scope)
ser.setBaud(VITA_UART0_BAUD)

# set glitch parameters
# trigger glitches with external trigger
scope.glitch.trigger_src = 'ext_continuous'
scope.glitch.output = 'enable_only'
scope.io.hs2 = 'clkgen'

# enable trigger
scope.advancedSettings.cwEXTRA.setTriggerModule(CWExtraSettings.MODULE_DECODEIO)
scope.advancedSettings.cwEXTRA.setTargetGlitchOut('A', True)

# init
target.init()

print('Starting glitch...')
success = False
while not success:
    for offset in xrange(MIN_OFFSET, MAX_OFFSET+1, OFFSET_STEP):
        # set offset from trigger
        scope.glitch.ext_offset = offset
        for width in xrange(MIN_WIDTH, MAX_WIDTH+1, WIDTH_STEP):
            print('trying offset {}, width {}'.format(offset, width))

            # reset
            scope.glitch.repeat = width

            times_glitched = 0

            while times_glitched == 0:
                # power on
                print('Waiting for Vita to power on...')
                scope.io.nrst = 'low'
                scope.io.pdid = 'low'
                time.sleep(POWER_ON_HOLD)
                scope.io.pdid = 'disabled'
                scope.io.nrst = 'disabled'

                timeout = GLITCH_FIND_TIMEOUT
                last_dat = ''
                while not success and timeout > 0:
                    mmc_cnt = mmc.count()
                    ser_cnt = ser.inWaiting()
                    while mmc_cnt > 0 or ser_cnt > 0:
                        if mmc_cnt > 0:
                            pkt = mmc.read()
                        if ser_cnt > 0:
                            dat = ser.read(ser_cnt, 0)
                            full_dat = last_dat + dat
                            last_dat = dat
                            if 'HI\r\n' in full_dat:
                                success = True
                                break
                            else:
                                print(dat, end="")
                                if 'complete\r\n' in full_dat:
                                    times_glitched += 1
                                    last_dat = ''
                        timeout = GLITCH_FIND_TIMEOUT
                        mmc_cnt = mmc.count()
                        ser_cnt = ser.inWaiting()
                    else:
                        timeout -= 1
                        time.sleep(0.1)

            print('Total times glitched: {}'.format(times_glitched))

            if success:
                break
        if success:
            break

# the rest of the data is available with the outputs, widths, and offsets lists
#glitch_display.display_table()
print('Glitch successful, waiting for UART data...')

f = None
if len(sys.argv) > 1:
    path = sys.argv[1]
    print('Dumping to {}'.format(path))
    f = open(path, "wb")

timeout = PAYLOAD_TIMEOUT
offset = 0
queue = []
while timeout > 0:
    count = ser.inWaiting()
    while count > 0:
        timeout = PAYLOAD_TIMEOUT
        dat = ser.read(count, 0)
        queue.extend(dat)
        if f:
            f.write(dat)
            f.flush()
        if (not f or VERBOSE) and len(queue) >= 16:
            print(hexdump(queue[0:16], offset), end="")
            queue = queue[16:]
            offset += 16
        count = ser.inWaiting()
    else:
        time.sleep(0.1)
        timeout -= 1
    while VERBOSE and mmc.count() > 0:
        pkt = mmc.read()
        print(str(pkt))

if f:
    f.close()

print('Timed out.')
