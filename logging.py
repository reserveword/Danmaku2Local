#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

import logging
logger = logging.Logger('danmaku2local', 'INFO')
def __init():
    import sys
    fmt = logging.Formatter('[%(levelname)s] %(filename)s:%(lineno)d: %(message)s', None, '%')
    if not logger.hasHandlers():
        logger.addHandler(logging.StreamHandler(sys.stdout))
    h = None
    for h in logger.handlers:
        h.setFormatter(fmt)
__init()
del logging, __init