import datetime
import inspect
import logging
from math import floor
import os
import sys
import queue

import numpy as np

from hyzou.LiveTrading import settings, utils
from botcoin.common.events import SignalEvent


class Strategy(object):


    def before_open(self):
        pass

    def after_close(self):
        pass