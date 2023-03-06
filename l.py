#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

import os
from ass import Document, Style, line as assline, parse_string, parse_file
from bisect import bisect
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from functools import total_ordering
from io import BytesIO, FileIO, TextIOWrapper
from sortedcontainers.sortedlist import SortedList
from typing import BinaryIO, Callable, Collection, Generator, Generic, List, Mapping, Optional, Self, TextIO, TypeAlias, TypeVar

from d2l import magic_number
from d2l.storage import filein
from d2l.tagging import DanmakuFileTagCompound, SubtitleTagCompound, TagCompound, VideoTagCompound

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
    joined: Document = Document()
    for k, v in subtitle.sections.items():
        joined.sections[k] = v.copy()
    if tl is None:
        tl = TimeLine()
    joined.styles += danmaku.styles
    for l in danmaku.events:
        line = l.line
        line.start = tl.get(line.start)  # type: ignore
        line.end = tl.get(line.end)  # type: ignore
        if line.start > line.end:  # just in case
            line.start, line.end = line.end, line.start
        joined.events.append(l.line)
    return joined


def tostr(x):
    if type(x) is str:
        return x
    elif type(x) is bytes:
        return x.decode()
    elif type(x) is bytearray:
        return x.decode()
    else:
        return str(x)


# def toass(src) -> Document:
#     if type(src) is bytes:
#         return parse_string(src.decode('utf-8'))
#     if type(src) is str:
#         if ':' in src:  # ass文件肯定有冒号，文件名不可能有冒号
#             return parse_string(src)
#         with open(src, 'r', encoding='utf-8') as file:
#             return parse_file(file)
#     if isinstance(src, (list, Generator, zip)):
#         return parse_file(tostr(j) for j in src)
#     if isinstance(src, TextIO):
#         return parse_file(src)
#     if isinstance(src, (BytesIO, BinaryIO, FileIO)):
#         return parse_file(TextIOWrapper(src))
#     raise RuntimeError('failed to convert to ass Document')

class FileType(Enum):
    UNKNOWN = 0
    VIDEO = 1
    SUBTITLE = 2
    DANMAKU = 3

class RuleType(Enum):
    MAGIC_NUMBER = 0
    MIME = 1
    EXT = 2

_video_ext = {
    '.mp4',
    '.m4v',
    '.mov',
    '.qt',
    '.avi',
    '.flv',
    '.wmv',
    '.asf',
    '.mpeg',
    '.mpg',
    '.vob',
    '.mkv',
    '.asf',
    '.wmv',
    '.rm',
    '.rmvb',
    '.vob',
    '.ts',
    '.dat',
}
_subtitle_ext = {'.ass', '.srt', '.smi', '.ssa', '.sub', '.stl', '.idx'}
_danmaku_ext = {'.xml', '.json', '.protobuf'}
_rule_ext: Mapping[str, FileType] = dict(**{ext:FileType.VIDEO for ext in _video_ext}, **{ext:FileType.SUBTITLE for ext in _subtitle_ext}, **{ext:FileType.DANMAKU for ext in _danmaku_ext})
def rule_ext(name: str) -> FileType:
    return _rule_ext.get(os.path.splitext(name)[1], FileType.UNKNOWN)

def rule_magic(name:str) -> FileType:
    with filein(name, 'rb') as f:
        return FileType.VIDEO if magic_number.video(f) else FileType.UNKNOWN

rules: list[Callable[[str], FileType]] = [rule_magic, rule_ext]

def dir() -> dict[FileType, set[str]]:
    rs: dict[FileType, set[str]] = {
        FileType.UNKNOWN: set(),
        FileType.VIDEO: set(),
        FileType.SUBTITLE: set(),
        FileType.DANMAKU: set(),
    }
    for file in os.listdir():
        if os.path.isfile(file):
            for r in rules:
                t = r(file)
                if t is not FileType.UNKNOWN:
                    rs[t].add(file)
    return rs

def l(names: set[str]) -> tuple[list[VideoTagCompound], list[SubtitleTagCompound]]:
    videoli = [VideoTagCompound(name) for name in names]
    assli = sum((video.subtitles for video in videoli if video.subtitles is not None), [])
    return videoli, assli

def d(names: set[str]) -> list[DanmakuFileTagCompound]:
    return [DanmakuFileTagCompound(name) for name in names]