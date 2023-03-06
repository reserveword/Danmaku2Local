#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

from os import PathLike
from typing import Callable, Iterable, Mapping, TypeAlias

from d2l.bilixml import av, bv, comments, ep, md, ss, code, cid, parsecomments
from d2l.danmaku2ass import Comment
from d2l.storage import LocalStorage
from d2l.tagging import DanmakuTagCompound

SingleDanmaku: TypeAlias = Callable[[str|int, PathLike | str], Iterable[Comment]]
MultiDanmaku: TypeAlias = Callable[[str|int, Iterable[PathLike|str]], Iterable[Comment]]

def multi(single: SingleDanmaku) -> MultiDanmaku:
    def multidanmaku(code: str|int, names: Iterable[PathLike|str]) -> Iterable[Comment]:
        m: Mapping[Comment, Iterable[Comment]] = {}
        for name in names:
            i = single(code, name)
            for d in i:
                if d not in m: # 去重
                    m[d] = i
                    yield d
                    break
        while len(m):
            _,v = m.popitem()
            for d in v:
                if d not in m: # 如果真的有完全相同的多条弹幕，取同一文件内出现次数最多的为准
                    m[d] = v
                    yield d
                    break
    return multidanmaku


def r(_code: str, pattern='{batch:003}_{cid}.{tag}.xml', siz=10) -> list[DanmakuTagCompound]:
    tag = LocalStorage()['tag']
    l = []
    for meta in code(_code):
        commentli = list(multi(comments)(meta.cid, (pattern.format(batch=i, cid=meta.cid, tag=tag) for i in range(siz))))
        l.append(DanmakuTagCompound(meta, commentli))
    return l