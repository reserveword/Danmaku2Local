#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

from functools import wraps
from typing import Mapping, Sequence, TypeVar

_T = TypeVar('_T')
_KT = TypeVar('_KT')
_VT = TypeVar('_VT')
_ST = TypeVar('_ST', bound=Sequence)

def singleton(clas: _T) -> _T:
    _instance = None
    new = clas.__new__
    @wraps(clas.__new__)
    def __new__(cls, *args, **kwargs):
        nonlocal _instance
        if _instance is None:
            _instance = new(cls, *args, **kwargs)
        return _instance
    clas.__new__ = __new__
    return clas

class frozendict(dict[_KT, _VT], Mapping[_KT, _VT]):
    _hash_cached = None
    _has_inited = False
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        self._has_inited = True
    def __setitem__(self, __key: _KT, __value: _VT) -> None:
        if self._has_inited:
            raise NotImplementedError('immutable!')
        return super().__setitem__(__key, __value)
    def __delitem__(self, __key: _KT) -> None:
        if self._has_inited:
            raise NotImplementedError('immutable!')
        return super().__delitem__(__key)
    def setdefault(self, *args, **kwargs):
        if self._has_inited:
            raise NotImplementedError('immutable!')
        return super().setdefault(*args, **kwargs)
    def popitem(self) -> tuple[_KT, _VT]:
        if self._has_inited:
            raise NotImplementedError('immutable!')
        return super().popitem()
    def pop(self, *args, **kwargs):
        if self._has_inited:
            raise NotImplementedError('immutable!')
        return super().pop(*args, **kwargs)
    def __hash__(self) -> int:
        if self._hash_cached is None:
            self._hash_cached = hash(tuple((k, v) for k, v in self.items()))
        return self._hash_cached

def getint(s: str) -> int:
    if s.isdecimal():
        return int(s)
    head = -1
    for i, c in enumerate(s):
        if head == -1:
            if c in '0123456789':
                head = i
        else:
            if c not in '0123456789':
                return int(s[head:i])
    if head == -1:
        return 0
    return int(s[head:])

def lcseq(a: _ST,b: _ST) -> Sequence:
    besttail = -1
    bestscore = 0
    r = []
    for aa in a:
        l = []
        for bb in b:
            if aa == bb:
                if not len(r) or not len(l):
                    score = 1
                else:
                    score = r[-1][len(l)-1] + 1
                l.append(score)
                if score > bestscore:
                    bestscore = score
                    besttail = len(l)
            else:
                l.append(0)
        r.append(l)
    return b[besttail - bestscore: besttail]