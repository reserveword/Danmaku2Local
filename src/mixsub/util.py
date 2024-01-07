#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import wraps
import logging
import os
import re
import sys
from typing import _ProtocolMeta, Generic, Iterable, Iterator, Mapping, Protocol, Self, Sequence, TypeVar, runtime_checkable
from ass.data import _WithFieldMeta


_T = TypeVar('_T')
_T2 = TypeVar('_T2') # pylint: disable=C0103
_KT = TypeVar('_KT')
_VT = TypeVar('_VT')
_T_contra = TypeVar("_T_contra", contravariant=True)
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

class FrozenDict(dict[_KT, _VT], Mapping[_KT, _VT]):
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
                if not r or not l:
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

def looping(obj: _T) -> Iterable[_T]:
    while True:
        yield obj

class Filter(Generic[_T]):
    @abstractmethod
    def test(self, o: _T) -> bool: ...

    def __add__(self, o: 'Filter[_T]|int|None') -> 'Filter[_T]':
        if o is None:
            return self
        if isinstance(o, int):
            return self
        return AndFilter(self, o)

    def __radd__(self, o: 'Filter[_T]|int|None') -> 'Filter[_T]':
        if o is None:
            return self
        if isinstance(o, int):
            return self
        return AndFilter(o, self)

    @staticmethod
    def test_filter(filter_: 'Filter[_T2]', obj: _T2) -> bool:
        return filter_.test(obj)


class DummyFilter(Filter[_T]):
    def test(self, o: _T) -> bool:
        return True

class AndFilter(Filter[_T]):
    filters: list[Filter[_T]]
    def __init__(self, *filters: Filter[_T]) -> None:
        self.filters = list(filters)
        super().__init__()
    def __iadd__(self, o: 'Filter[_T]') -> Self:
        self.filters.append(o)
        return self
    def test(self, o: _T) -> bool:
        return all(map(Filter.test_filter, self.filters, looping(o)))

class OrFilter(Filter[_T]):
    filters: list[Filter[_T]]
    def __init__(self, *filters: Filter[_T]) -> None:
        self.filters = list(filters)
        super().__init__()
    def __iadd__(self, o: 'Filter[_T]') -> Self:
        self.filters.append(o)
        return self
    def test(self, o: _T) -> bool:
        return all(map(Filter.test_filter, self.filters, looping(o)))

class RegexFilter(Filter[str]):
    pattern: re.Pattern
    def __init__(self, s: str):
        self.pattern = re.compile(s)
        super().__init__()

    def test(self, o: str) -> bool:
        return self.pattern.search(o) is not None
class SupportsLT(Protocol[_T_contra]):
    def __lt__(self, __other: _T_contra) -> bool: ...

_SupportsLtT = TypeVar('_SupportsLtT', bound=SupportsLT)

def union(*iterables: Iterable[_SupportsLtT]) -> Iterable[_SupportsLtT]:
    return unionsorted(*(sorted(it) for it in iterables))

@dataclass
class PeekableIterator(Generic[_T]):
    head: _T
    tail: Iterator[_T]
    flag: bool = False
    def __init__(self, it: Iterable[_T]) -> None:
        self.tail = iter(it)
    def peek(self) -> _T:
        if not self.flag:
            self.head = next(self.tail)
            self.flag = True
        return self.head
    def pop(self) -> _T:
        if self.flag:
            self.flag = False
            return self.head
        return next(self.tail)

def unionsorted(*lis: list[_SupportsLtT]) -> Iterable[_SupportsLtT]:
    if len(lis) > 2:
        mid = len(lis) // 2
        l, r = PeekableIterator(unionsorted(*lis[:mid])), PeekableIterator(unionsorted(*lis[mid:]))
    elif len(lis) == 2:
        l, r = PeekableIterator(lis[0]), PeekableIterator(lis[1])
    elif len(lis) == 1:
        for c in lis[0]:
            yield c
        return
    else:
        return
    try:
        now: PeekableIterator[_SupportsLtT] = l
        hold: PeekableIterator[_SupportsLtT] = r
        while True:
            if now.peek() < hold.peek():
                yield now.pop()
            elif now.peek() == hold.peek():
                yield now.pop()
                hold.pop()
            else:
                now, hold = hold, now
    except StopIteration:
        # 反正最多只有一个有数据，谁先谁后不要紧
        try:
            while True:
                yield l.pop()
        except StopIteration:
            pass
        try:
            while True:
                yield r.pop()
        except StopIteration:
            pass

def seekzero(func):
    '''decorative for auto reset file cursor'''
    def decorated_function(file_):
        file_.seek(0)
        try:
            return func(file_)
        finally:
            file_.seek(0)
    return decorated_function


def makeprefix(src, dst: str, on=True) -> str:
    if type(src != str):
        src = str(src)
    if on:
        if not src.startswith(dst):
            src = dst + str(src)
    else:
        if src.startswith(dst):
            src = src[len(dst) :]
    return src


def prefix(*pfxs: str, on=True, **kwpfxs: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i, pfx in enumerate(pfxs):
                if pfx is not None and len(args) > i:
                    if not isinstance(args, list):
                        args = list(args)
                    args[i] = makeprefix(args[i], pfx, on=on)
            for k, pfx in kwpfxs.items():
                if pfx is not None and k in kwargs:
                    kwargs[k] = makeprefix(kwargs[k], pfx, on=on)
            return func(*args, **kwargs)

        return wrapper

    return decorator

logger = logging.Logger('danmaku2local', 'INFO')
def __init():
    fmt = logging.Formatter('[%(levelname)s] %(filename)s:%(lineno)d: %(message)s', None, '%')
    if not logger.hasHandlers():
        logger.addHandler(logging.StreamHandler(sys.stdout))
    h = None
    for h in logger.handlers:
        h.setFormatter(fmt)
__init()
del __init


def throw(e: Exception):
    raise e

class FileType(Enum):
    UNKNOWN = 0
    VIDEO = 1
    SUBTITLE = 2
    DANMAKU = 3


_video_ext = {
    '.mp4',
    '.m4v',
    '.mov',
    '.qt',
    '.avi',
    '.flv',
    '.wmv',
    '.mpeg',
    '.mpg',
    '.vob',
    '.mkv',
    '.asf',
    '.rm',
    '.rmvb',
    '.ts',
    '.dat',
}
_subtitle_ext = {'.ass', '.srt', '.smi', '.ssa', '.sub', '.stl', '.idx'}
_danmaku_ext = {'.xml', '.json', '.protobuf'}
_filetype_ext = {
    FileType.DANMAKU: _danmaku_ext,
    FileType.SUBTITLE: _subtitle_ext,
    FileType.VIDEO: _video_ext,
}

# def rule_magic(name:str) -> FileType:
#     with filein(name, 'rb') as f:
#         return FileType.VIDEO if magic_number.video(f) else FileType.UNKNOWN

def thisdir(filetype: FileType, path = None) -> set[str]:
    rs: set[str] = set()
    file_ext = _filetype_ext[filetype]
    for file in os.listdir(path):
        if os.path.isfile(file) and os.path.splitext(file)[1] in file_ext:
            rs.add(file)
    return rs

@dataclass
class LocalFile:
    path: str
    def __post_init__(self):
        path, self._name = os.path.split(self.path)
        self._basename, self._extname = os.path.splitext(self._name)
        self._path = os.path.abspath(path)

    @property
    def name(self) -> str:
        return self._name

    @property
    def pathname(self) -> str:
        return self._path

    @property
    def basename(self) -> str:
        return self._basename

    @property
    def extname(self) -> str:
        return self._extname

@runtime_checkable
class NeedResize(Protocol):
    def resize(self, width: int, height: int) -> None:
        ...

class MyMetaClass(_WithFieldMeta, _ProtocolMeta):
    pass
