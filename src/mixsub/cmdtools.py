#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

from mixsub.dests.video import LocalVideoSeries
from mixsub.sources import AbbrMixSourceSeries


cmd = {
    'r': AbbrMixSourceSeries,
    'l': LocalVideoSeries,
}