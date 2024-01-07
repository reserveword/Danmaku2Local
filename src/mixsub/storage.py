#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

from io import TextIOWrapper
import os
import pickle
from typing import IO, Any, BinaryIO, Iterable, Literal, Protocol, Self, TypeAlias, TypeVar, overload

import chardet

from mixsub.util import logger, singleton

_KT = TypeVar('_KT')
_VT = TypeVar('_VT')
_VT_co = TypeVar('_VT_co', covariant=True)

# stable
class SupportsKeysAndGetItem(Protocol[_KT, _VT_co]):
    def keys(self) -> Iterable[_KT]: ...
    def __getitem__(self, __key: _KT) -> _VT_co: ...


class ConfigStorage(dict[_KT, _VT]):
    name = 'config.pickle'
    path: str = ''
    # @overload
    # def __init__(self, __name: Optional[str]=None) -> None: ...
    # @overload
    # def __init__(self: dict[str, _VT], *, __name: Optional[str]=None, **kwargs: _VT) -> None: ...
    # @overload
    # def __init__(self, __map: SupportsKeysAndGetItem[_KT, _VT], __name: Optional[str]=None) -> None: ...
    # @overload
    # def __init__(self: dict[str, _VT], __map: SupportsKeysAndGetItem[str, _VT], *, __name: Optional[str]=None, **kwargs: _VT) -> None: ...
    # @overload
    # def __init__(self, __iterable: Iterable[tuple[_KT, _VT]], __name: Optional[str]=None) -> None: ...
    # @overload
    # def __init__(self: dict[str, _VT], __iterable: Iterable[tuple[str, _VT]], *, __name: Optional[str]=None, **kwargs: _VT) -> None: ...
    # @overload
    # def __init__(self: dict[str, str], __iterable: Iterable[list[str]], __name: Optional[str]=None) -> None: ...
    # def __init__(self, *args, **kwargs) -> None:
    #     super().__init__(*args, **kwargs)
    def __new__(cls: type[Self], *args: Any, **kwargs: Any) -> Self:
        self = super().__new__(cls, *args, **kwargs)
        self.load()
        return self

    def dump(self) -> None:
        with open(self.path, 'wb') as f:
            pickle.dump(dict(self), f)

    def load(self) -> Self:
        try:
            with open(self.path, 'rb') as f:
                obj: dict = pickle.load(f)
        except (pickle.UnpicklingError, FileNotFoundError) as e:
            logger.debug(e)
            return self
        self.clear()
        self.update(obj)
        return self

@singleton
class GlobalStorage(ConfigStorage):
    name = 'danmaku2global.pickle'
    __default = {
        'tag': 'danmaku',
        'style': {
            'density': 0.85,
            'covered_rate': 1.0,
            'rows': 36,
            'fontface': 'SimHei',
            'fontsize': 50.0,
            'alpha': int(0.6*255),
            'duration_marquee': 5.0,
            'duration_still': 5.0,
            'filters_regex': (),
            'reduced': False,
        }
    }
    _global: str
    def __init__(self, name = None) -> None:
        if name is not None:
            self.name = name
        if not hasattr(self, '_global'):
            self.findglobal()
        super().__init__()

    def setglobal(self, path: os.PathLike | str):
        self._global = os.path.abspath(path)
        self.path = os.path.join(self._global, self.name)

    def findglobal(self):
        self.setglobal(os.path.expanduser('~'))

    def __missing__(self, __key):
        return self.__default[__key]

    def load(self) -> Self:
        self.findglobal()
        return super().load()

    def dump(self):
        self.findglobal()
        super().dump()

@singleton
class LocalStorage(ConfigStorage):
    name = 'danmaku2local.pickle'
    _local: str
    def __init__(self, name = None) -> None:
        if name is not None:
            self.name = name
        if not hasattr(self, '_local'):
            self.findlocal()
        self.__global = GlobalStorage()
        super().__init__()

    def setlocal(self, path: os.PathLike | str):
        self._local = os.path.abspath(path)
        self.path = os.path.join(self._local, self.name)

    def findlocal(self):
        self.setlocal('.')

    def getlocal(self) -> os.PathLike | str:
        return self._local

    def __missing__(self, __key):
        return self.__global[__key]

    def load(self) -> Self:
        self.findlocal()
        return super().load()

    def dump(self):
        self.findlocal()
        super().dump()


L = LocalStorage
G = GlobalStorage

OpenTextMode: TypeAlias = Literal['r+', '+r', 'rt+', 'r+t', '+rt', 'tr+', 't+r', '+tr', 'w+', '+w', 'wt+', 'w+t', '+wt', 'tw+', 't+w', '+tw', 'a+', '+a', 'at+', 'a+t', '+at', 'ta+', 't+a', '+ta', 'x+', '+x', 'xt+', 'x+t', '+xt', 'tx+', 't+x', '+tx', 'w', 'wt', 'tw', 'a', 'at', 'ta', 'x', 'xt', 'tx', 'r', 'rt', 'tr', 'U', 'rU', 'Ur', 'rtU', 'rUt', 'Urt', 'trU', 'tUr', 'Utr']
OpenBinaryMode: TypeAlias = Literal['rb+', 'r+b', '+rb', 'br+', 'b+r', '+br', 'wb+', 'w+b', '+wb', 'bw+', 'b+w', '+bw', 'ab+', 'a+b', '+ab', 'ba+', 'b+a', '+ba', 'xb+', 'x+b', '+xb', 'bx+', 'b+x', '+bx', 'rb', 'br', 'rbU', 'rUb', 'Urb', 'brU', 'bUr', 'Ubr', 'wb', 'bw', 'ab', 'ba', 'xb', 'bx']

def pathlocal(name: str) -> str:
    return os.path.join(LocalStorage().getlocal(), name)

@overload
def filelocal(name, mode: OpenTextMode, encoding='utf-8', **kwargs) -> TextIOWrapper: ...
@overload
def filelocal(name, mode: OpenBinaryMode, encoding='utf-8', **kwargs) -> BinaryIO: ...
@overload
def filelocal(name, mode: str, encoding='utf-8', **kwargs) -> IO[Any]: ...
def filelocal(name, mode, encoding: str='utf-8', **kwargs):
    if 'b' in mode:
        return open(pathlocal(name), mode) # pylint: disable=unspecified-encoding
    return open(pathlocal(name), mode, encoding=encoding, **kwargs)

@overload
def filein(name, **kwargs) -> TextIOWrapper: ...
@overload
def filein(name, mode: OpenTextMode, **kwargs) -> TextIOWrapper: ...
@overload
def filein(name, mode: OpenBinaryMode, **kwargs) -> BinaryIO: ...
def filein(name, mode='r', **kwargs):
    encoding = 'utf-8'
    try:
        with open(pathlocal(name), 'rb') as f:
            header = f.read(1000)
        guess = chardet.detect(header)['encoding']
        if isinstance(guess, str):
            if guess in ('ascii', 'Windows-1254'):
                guess = 'utf-8'
            encoding = guess
    except Exception as e: # pylint: disable=broad-exception-caught
        logger.warning(e)
    return filelocal(name, mode, encoding=encoding, **kwargs)

@overload
def fileout(name) -> TextIOWrapper: ...
@overload
def fileout(name, mode: OpenTextMode) -> TextIOWrapper: ...
@overload
def fileout(name, mode: OpenBinaryMode) -> BinaryIO: ...
def fileout(name, mode='w'):
    d = os.path.dirname(name)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    return filelocal(name, mode)
