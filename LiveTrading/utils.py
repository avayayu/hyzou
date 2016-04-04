import datetime
import itertools
import logging
import numpy as np
import pandas as pd
import os
import sys
import traceback

ROUND_DECIMALS = 2
ROUND_DECIMALS_BELOW_ONE = 3

def optimize(*args):
    """
        Returns all possible combinations of multiple np.arange values based on
        tuples passed to this method. Exposed externally, to be used in backtesting.
    """
    if not args:
        return
    elif len(args) == 1:
        a = args[0]
        return np.arange(a[0],a[1],a[2])
    else:
        lists_of_elements = [np.arange(a[0],a[1],a[2]) for a in args]
        return list(itertools.product(*lists_of_elements))

def _round(value):
    if value >= 1:
        return np.round(value, ROUND_DECIMALS)
    else:
        return np.round(value, ROUND_DECIMALS_BELOW_ONE)

def _delta_is_one_business_day(date1, date2):
    # Checks last local historical data available and verifies if it
    # is too old ( >=4 days delta on monday, >= 3 on sunday,, >=2 every for the rest)
    delta = date1-date2
    if date1.weekday() == 0:  # monday
        data_is_old = True if delta >= datetime.timedelta(days=4) else False
    elif date1.weekday() == 6:  # sunday
        data_is_old = True if delta >= datetime.timedelta(days=3) else False
    else:
        data_is_old = True if delta >= datetime.timedelta(days=2) else False

    return False if data_is_old else True

def _basic_config(verbose=None):
    # Logging
    verbosity = 10 if verbose else 20
    log_format = '# %(levelname)s - %(message)s'
    logging.basicConfig(format=log_format, level=verbosity)

    # Pandas
    pd.set_option('display.max_rows', 200)
    pd.set_option('display.width', 1000)

def _log_exception(exc_type=None, exc_obj=None, exc_tb=None):
    if not (exc_type and exc_obj and exc_tb):
        exc_type, exc_obj, exc_tb = sys.exc_info()
    if exc_tb:
        tb = traceback.extract_tb(exc_tb)[-1]
        filename = tb[0]
        line = tb[1]
        logging.critical("Exception {} on {} line {} - {}".format(exc_type, filename, line, exc_obj))
    else:
        logging.critical("utils._log_exception was called but there is not exception traceback")
