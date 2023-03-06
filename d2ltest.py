#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

import os

from d2l import *


# os.chdir('D:\\Videos\\[VCB-Studio] Haiyore! Nyaruko-san\\[VCB-Studio] Haiyore! Nyaruko-san [Ma10p_1080p]')
# storage.LocalStorage.findlocal()
# dir = l.dir()
# v, s1 = l.l(dir[l.FileType.VIDEO])
# s2 = ass.ass(dir[l.FileType.SUBTITLE])
# # d1 = r.r('??????')
# d2 = l.d(dir[l.FileType.DANMAKU])
# v, d, s = v, d2, s1+s2
# del s1,s2,d2
# # storage.LocalStorage()['vds'] = (v,d,s)
# seq, singular = tagging.match(v, d, s)
# for vv, dd, ss in seq + singular:
#     name = os.path.extsep.join((os.path.splitext(vv.val)[0], storage.LocalStorage()['tag'], 'ass'))
#     with storage.fileout(name) as f:
#         ssdoc = ass.toass(ss)
#         width, height = ssdoc.play_res_x, ssdoc.play_res_y
#         dddoc = ass.toass(dd, width=width, height=height)
#         ass.assjoindanmaku(ssdoc, dddoc).dump_file(f)