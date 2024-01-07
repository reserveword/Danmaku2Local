#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

import re
from typing import Callable, Dict

from mixsub.schema.models import MixSourceSeries
from mixsub.sources.danmaku import acfun, bili


_SourceMatcher: Dict[str, Callable[[str], MixSourceSeries]] = {
    r'av\d+': bili.av,
    r'BV\w+': bili.bv,
    r'ss\d+': bili.ss,
    r'ep\d+': bili.ep,
    r'md\d+': bili.md,
    r'ac\d+': acfun.ac,
    r'aa\d+': acfun.aa,
}

def AbbrMixSourceSeries(name: str) -> MixSourceSeries: # pylint: disable=invalid-name
    """根据缩写字符串获取混入字幕的数据源系列。支持bilibili av/BV/ss/ep号或acfun ac/aa号作为数据源*系列*"""
    for pattern, get in _SourceMatcher.items():
        if re.fullmatch(pattern, name):
            return get(name)
    raise RuntimeError('unknown code type')
