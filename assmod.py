#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

from ass import Document, Style, line as assline, parse_string, parse_file, FieldSection, LineSection
from bisect import bisect
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from functools import total_ordering
from io import BytesIO, FileIO, TextIOWrapper
from sortedcontainers.sortedlist import SortedList
from typing import BinaryIO, Generator, Generic, List, Optional, Self, TextIO, TypeAlias, TypeVar

from d2l.bilixml import parsecomments, tocomments
from d2l.tagging import SubtitleTagCompound, BiliSortTag, DummySortTag, SortTag, XmlSortTag
from d2l.storage import filein

_AssEventType: TypeAlias = (
    assline.Dialogue
    | assline.Comment
    | assline.Picture
    | assline.Sound
    | assline.Movie
    | assline.Command
)


_T = TypeVar('_T')


@dataclass
class AssLine(Generic[_T]):
    line: _T

    def __eq__(self, __o: object) -> bool:
        if type(__o) is not type(self):
            return False
        return frozenset(self.line.__dict__.items()) == frozenset(__o.line.__dict__.items())
        # oline = __o.line.__dict__
        # olinenum = len(oline)
        # for k, v in self.line.__dict__.items():
        #     if k in oline and oline[k] == v:
        #         olinenum -= 1
        #         continue
        #     return False
        # if olinenum is not 0:
        #     return False
        # return True

    def __hash__(self) -> int:
        return frozenset(self.line.__dict__.items()).__hash__()


class CompareError(RuntimeError):
    pass


class TimeDirection(Enum):
    L = -1
    E = 0
    G = 1
    # def __lt__(self, cmp: Self): bool:
    #     if


@total_ordering
class TimePin:
    def __init__(self, pinned: timedelta, pinon: timedelta, direction: TimeDirection):
        self.pinned = pinned
        self.pinon = pinon
        self.direction = direction

    def __lt__(self, cmp: Self) -> bool:
        if self.pinned < cmp.pinned:
            return True
        elif self.pinned == cmp.pinned and self.pinon < cmp.pinon:
            return True
        elif (
            self.pinned == cmp.pinned
            and self.pinon == cmp.pinon
            and self.direction.value < cmp.direction.value
        ):
            return True
        return False

    #     if self.pinned < cmp.pinned and self.pinon <= cmp.pinon:
    #         return True
    #     elif self.pinned <= cmp.pinned and self.pinon < cmp.pinon:
    #         return True
    #     elif self.pinned == cmp.pinned and self.pinon == cmp.pinon and self.direction.value < cmp.direction.value:
    #         return True
    #     if self.conflicts(cmp):
    #         raise CompareError('TimePin Conflicts!', self, cmp)
    #     return False
    # def conflicts(self, cmp: Self) -> bool:
    #     if self.pinned < cmp.pinned and self.pinon > cmp.pinon:
    #         return True
    #     elif self.pinned > cmp.pinned and self.pinon < cmp.pinon:
    #         return True
    #     return False


class TimeLine:
    def __init__(self) -> None:
        self.pins: SortedList = SortedList()

    def pin(self, pinned: timedelta, pinon: timedelta):
        # self.pins.add(TimePin(pinned, pinon, TimeDirection.E))
        self.pins.add(TimePin(pinned, pinon, TimeDirection.G))
        self.pins.add(TimePin(pinned, pinon, TimeDirection.L))

    def push(self, pinned: timedelta, pinon: timedelta):
        self.pins.add(TimePin(pinned, pinon, TimeDirection.G))

    def pull(self, pinned: timedelta, pinon: timedelta):
        self.pins.add(TimePin(pinned, pinon, TimeDirection.L))

    def get(self, pinned: timedelta) -> timedelta:
        pin = TimePin(pinned, pinned, TimeDirection.E)
        bias = self.pins.bisect(pin)
        if len(self.pins) == 0:
            return pinned
        elif len(self.pins) <= bias:
            left: TimePin = self.pins[-1]  # type: ignore
            if left.direction is TimeDirection.L:
                return pinned
            return pinned + left.pinon - left.pinned
        elif len(self.pins) == bias:
            left: TimePin = self.pins[bias]  # type: ignore
            if left.direction is TimeDirection.L:
                return pinned
            return pinned + left.pinon - left.pinned
        else:
            left: TimePin = self.pins[bias]  # type: ignore
            right: TimePin = self.pins[bias + 1]  # type: ignore
            if right.direction is TimeDirection.G:
                if left.direction is TimeDirection.L:
                    return pinned
                return left.pinon + pinned - left.pinned
            # 时间轴放缩
            return left.pinon + (pinned - left.pinned) * (
                (right.pinon - left.pinon) / (right.pinned - left.pinned)
            )

    def reverseget(self, pinon: timedelta) -> timedelta:
        bias = bisect(self.pins, pinon, key=lambda x: x.pinon)  # type: ignore
        if len(self.pins) == 0:
            return pinon
        elif len(self.pins) <= bias:
            left: TimePin = self.pins[-1]  # type: ignore
            if left.direction is TimeDirection.L:
                return pinon
            return left.pinon + pinon - left.pinned
        elif len(self.pins) == bias:
            left: TimePin = self.pins[bias]  # type: ignore
            if left.direction is TimeDirection.L:
                return pinon
            return left.pinon + pinon - left.pinned
        else:
            left: TimePin = self.pins[bias]  # type: ignore
            right: TimePin = self.pins[bias + 1]  # type: ignore
            if right.direction is TimeDirection.G:
                if left.direction is TimeDirection.L:
                    return pinon
                return left.pinon + pinon - left.pinned
            # 时间轴放缩
            return left.pinned + (pinon - left.pinon) * (
                (right.pinned - left.pinned) / (right.pinon - left.pinon)
            )

    def merge(self, pin: TimePin):
        pinon = self.reverseget(pin.pinon)
        self.pins.add(TimePin(pin.pinned, pinon, pin.direction))

    def mergepin(self, pinned: timedelta, pinon: timedelta):
        # self.pins.add(TimePin(pinned, pinon, TimeDirection.E))
        self.merge(TimePin(pinned, pinon, TimeDirection.G))
        self.merge(TimePin(pinned, pinon, TimeDirection.L))

    def mergepush(self, pinned: timedelta, pinon: timedelta):
        self.merge(TimePin(pinned, pinon, TimeDirection.G))

    def mergepull(self, pinned: timedelta, pinon: timedelta):
        self.merge(TimePin(pinned, pinon, TimeDirection.L))


def assjoin(
    assli: List[Document], maindoc: Optional[Document] = None, tl: Optional[TimeLine] = None
) -> Document:
    joined: Document = Document()
    if maindoc is None:
        maindoc = assli[0]
        for k, v in maindoc.sections.items():
            joined.sections[k] = v.copy()
        joined.styles.clear()
        joined.events.clear()
    else:
        for k, v in maindoc.sections.items():
            joined.sections[k] = v.copy()
    if tl is None:
        tl = TimeLine()
    styles: set[AssLine[Style]] = set()
    events: set[AssLine[_AssEventType]] = set()
    for a in assli:
        for l in a.styles:
            styles.add(AssLine(l))
        for l in a.events:
            events.add(AssLine(l))
    for l in styles:
        joined.styles.append(l.line)
    for l in events:
        line = l.line
        line.start = tl.get(line.start)  # type: ignore
        line.end = tl.get(line.end)  # type: ignore
        joined.events.append(l.line)
    return joined


def assjoindanmaku(
    subtitle: Document, danmaku: Document, tl: Optional[TimeLine] = None
) -> Document:
    if tl is None:
        tl = TimeLine()
    subtitle.styles += danmaku.styles
    order = subtitle.events.field_order
    for line in danmaku.events:
        for f in order:
            line.fields.setdefault(f, '')
        line.start = tl.get(line.start)  # type: ignore
        line.end = tl.get(line.end)  # type: ignore
        if line.start > line.end:  # just in case
            line.start, line.end = line.end, line.start
        subtitle.events.append(line)
    return subtitle


def tostr(x):
    if type(x) is str:
        return x
    elif type(x) is bytes:
        return x.decode()
    elif type(x) is bytearray:
        return x.decode()
    else:
        return str(x)


def toass(src, **kwargs) -> Document:
    if isinstance(src, SortTag):
        if isinstance(src, DummySortTag):
            return Document()
        if isinstance(src, XmlSortTag):
            comments = tocomments(src.val, guess=True)
            return parsecomments(comments, **kwargs)
        if isinstance(src, BiliSortTag):
            return parsecomments(src.comments, **kwargs)
        src=src.val
    if isinstance(src, bytes):
        return parse_string(src.decode('utf-8'))
    if isinstance(src, str):
        if ':' in src:  # ass文件肯定有冒号，文件名不可能有冒号
            return parse_string(src)
        with filein(src) as file:
            return parse_file(file)
    if isinstance(src, (list, Generator, zip)):
        return parse_file(tostr(j) for j in src)
    if isinstance(src, TextIO):
        return parse_file(src)
    if isinstance(src, (BytesIO, BinaryIO, FileIO)):
        return parse_file(TextIOWrapper(src))
    raise RuntimeError('failed to convert to ass Document')

def ass(names: set[str]) -> list[SubtitleTagCompound]:
    return [SubtitleTagCompound(name) for name in names]