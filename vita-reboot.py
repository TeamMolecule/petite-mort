from __future__ import print_function, division

import time
import logging
import os
import csv

import chipwhisperer as cw
#from scripting_utils import GlitchResultsDisplay

logging.basicConfig(level=logging.WARN)
scope = cw.scope()
target = cw.target(scope)

# reset device
scope.io.nrst = 'low'
scope.io.nrst = 'disabled'
time.sleep(1.8)

# power on
scope.io.pdid = 'low'
time.sleep(1.8)
scope.io.pdid = 'disabled'

print('Done')
