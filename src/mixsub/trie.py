#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from io import StringIO
from typing import Any, Callable, Generic, Iterator, MutableSet, Optional, Protocol, Self, TypeVar, overload

_T = TypeVar('_T')
_T_co = TypeVar("_T_co", covariant=True)
_ST = TypeVar('_ST', bound=Sequence)
_VT = TypeVar('_VT')
_VT_co = TypeVar("_VT_co", covariant=True)

# stable
class SupportsKeysAndGetItem(Protocol[_ST, _VT_co]):
    def keys(self) -> Iterable[_ST]: ...
    def __getitem__(self, __key: _ST) -> _VT_co: ...

class _Dummy:
    pass

@dataclass
class _TrieNode(MutableSet[_ST], Generic[_T, _ST]):
    tail: int
    nxt: dict[_T, Self]
    val: _ST
    def isempty(self) -> bool:
        return len(self.nxt) == 0
    def isvalid(self) -> bool:
        return len(self.val) == self.tail
    def step(self, __key: Optional[_ST] = None, besteffort: bool = False) -> Optional[Self]:
        if len(self.nxt) == 0:
            return None
        if __key is None:
            return self.nxt.values().__iter__().__next__()
        if len(__key) <= self.tail:
            nxt = None
        else:
            real = __key[self.tail]
            nxt = self.nxt.get(real, None)
        if nxt is None and besteffort:
            return self.nxt.values().__iter__().__next__()
        else:
            return nxt
    def test(self, __key: _ST, startwith: int = 0) -> Self | int:
        realtail = min(len(__key), self.tail)
        for i in range(startwith, realtail):
            if __key[i] != self.val[i]:
                return i
        step = self.step(__key)
        if step is not None:
            return step
        return realtail
    def prefix(self, __key: _ST) -> Optional[_ST]:
        t = self.test(__key)
        best = None
        tail = self.tail
        while not isinstance(t, int):
            if t.isvalid():
                best = t.val
            tail, t = t.tail, t.test(__key, tail)
        return best
    def char_prefix(self, __key: _ST) -> int:
        t = self.test(__key)
        tail = self.tail
        while not isinstance(t, int):
            tail, t = t.tail, t.test(__key, tail)
        return t
    def add(self, __key: _ST):
        t = self.test(__key)
        last: Self | int = self
        while not isinstance(t, int):
            last, t = t, t.test(__key, last.tail)
        last._add_here(__key, t)
    def _add_here(self, __key: _ST, __tail: int):
        if self.tail == __tail:
            if len(__key) == __tail:
                self.val = __key
            else:
                self.nxt[__key[__tail]] = _TrieNode(len(__key), {}, __key)
            return
        nxt: dict[_T, _TrieNode] = self.nxt # type: ignore
        orinode = _TrieNode(self.tail, nxt, self.val)
        if len(__key) == __tail:
            self.nxt = {self.val[__tail]: orinode}
            self.val = __key
        else:
            keynode = _TrieNode(len(__key), {}, __key)
            self.nxt = {self.val[__tail]: orinode, __key[__tail]: keynode}
        self.tail = __tail
        # self.val # 保留供以后使用
        return
    def discard(self, value: _ST) -> None:
        raise NotImplementedError
        # not tested down here
        # if len(value) == self.tail:
        #     if value == self.val:
        #         # 就在这个节点上
        #         if self.isempty():
        #             self.tail = -1
        #         else:
        #             self.val = self.step().val # type: ignore # self非空的情况下step一定能返回下一个节点
        #     else:
        #         # 本来就不存在
        #         return
        # nxt = self.step(value)
        # if nxt is None:
        #     # 本来就不存在
        #     return
        # nxt.discard(value)
        # if nxt.tail == -1:
        #     del self.nxt[value[self.tail]]
        # if len(nxt.nxt) == 1 and not nxt.isvalid(): # 如果删除节点后的子节点只有一个子节点（而且没有叶子）就把这个子节点删掉，直接接上孙节点
        #     newnxt = nxt.step()
        #     self.nxt[nxt.val[self.tail]] = newnxt # type: ignore
    def __contains__(self, x: object) -> bool:
        if isinstance(x, Sequence):
            return self.prefix(x) == x # type: ignore
        return False
    def __iter__(self) -> Iterator[_ST]:
        stack = [self]
        while stack:
            n = stack.pop()
            if n.isvalid():
                yield n.val
            stack.extend(n.nxt.values())
    def __len__(self) -> int:
        return sum(map(len, self.nxt.values()), 1 if self.isvalid() else 0)
    def stringify(self, sio: StringIO, substringfy: Callable[[Any], str] = str, head: int = 0, getval: Optional[Callable[[_ST], str]] = None) -> None:
        sli = self.val[head:self.tail]
        sio.write(substringfy(sli))
        if getval is not None and self.isvalid():
            sio.write('(')
            sio.write(getval(self.val))
            sio.write(')')
        if not self.isempty():
            sio.write(':{')
            first = True
            for v in self.nxt.values():
                if first:
                    first = False
                else:
                    sio.write(', ')
                v.stringify(sio, substringfy, self.tail, getval)
            sio.write('}')
    def __str__(self):
        sio = StringIO()
        self.stringify(sio)
        return sio.getvalue()
    def __repr__(self):
        sio = StringIO()
        self.stringify(sio, substringfy=repr)
        return sio.getvalue()

class TrieSet(MutableSet[_ST]):
    root: Optional[_TrieNode[Any, _ST]] = None
    def __contains__(self, x: object) -> bool:
        if self.root is None:
            return False
        return x in self.root
    def __iter__(self) -> Iterator[_ST]:
        if self.root is None:
            return iter(())
        return iter(self.root)
    def __len__(self) -> int:
        if self.root is None:
            return 0
        return len(self.root)
    def add(self, value: _ST) -> None:
        if self.root is None:
            self.root = _TrieNode(len(value), {}, value)
        return self.root.add(value)
    def discard(self, value: _ST) -> None:
        raise NotImplementedError
        # if self.root is None:
        #     return
        # self.root.discard(value)
    def char_prefix(self, value: _ST) -> int:
        if self.root is None:
            return 0
        return self.root.char_prefix(value)

class Trie(MutableMapping[_ST, _VT]):
    def __init__(self, init: Optional[Mapping[_ST, _VT]] = None) -> None:
        self.dict: dict[_ST, _VT] = {}
        self.root: Optional[_TrieNode[Any, _ST]] = None
        if init is not None:
            for k, v in init.items():
                self[k] = v
    def match(self, __key: _ST) -> Optional[_ST]:
        if self.root is None:
            return None
        return self.root.prefix(__key)
    @overload
    def get(self, __key: _ST) -> _VT | None: ...
    @overload
    def get(self, __key: _ST, __default: _VT | _T) -> _VT | _T: ...
    def get(self, __key: _ST, __default: Optional[_VT|_T] = None) -> Optional[_VT|_T]:
        st = self.match(__key)
        if st is None:
            return __default
        return self.dict.get(__key, __default)
    def __getitem__(self, __key: _ST) -> _VT:
        st = self.match(__key)
        if st is None:
            raise KeyError(__key)
        return self.dict[st]
    def __setitem__(self, __key: _ST, __value: _VT) -> None:
        if self.root is None:
            self.root = _TrieNode(len(__key), {}, __key)
        else:
            self.root.add(__key)
        self.dict[__key] = __value
    def __delitem__(self, __key: _ST) -> None:
        raise NotImplementedError()
    def __iter__(self) -> Iterator[_ST]:
        if self.root is None:
            return ().__iter__()
        return self.root.__iter__()
    def __len__(self) -> int:
        return self.dict.__len__()
    def __repr__(self) -> str:
        if self.root is None:
            return self.__class__.__qualname__ + '()'
        sio = StringIO()
        sio.write(f'{self.__class__.__qualname__}(')
        self.root.stringify(sio, repr, getval=lambda x: repr(self.dict.get(x)))
        sio.write(')')
        return sio.getvalue()
    def __str__(self) -> str:
        if self.root is None:
            return self.__class__.__qualname__ + '()'
        sio = StringIO()
        sio.write(f'{self.__class__.__qualname__}(')
        self.root.stringify(sio, str, getval=lambda x: str(self.dict.get(x)))
        sio.write(')')
        return sio.getvalue()

# import importlib
# rel = importlib.reload
# if __name__ == '__main__':
#     a: Trie[str, str] = Trie()
#     t = Trie()
#     t['a'] = 1
#     t['b'] = 2
#     t['aa'] = 11
#     repr(t)