
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
import math
import os
import random
from typing import Any, Callable, Collection, Iterable, List, Optional, TextIO

import ass
from ass.data import Color, _Field

from mixsub.storage import LocalStorage, filein
from mixsub.util import MixSourceSet, MyMetaClass, NeedResize, logger

@dataclass
class DanmakuList(MixSourceSet):
    idx: int
    val: dict
    _tag: str = 'danmaku'
    src_dir: str = 'danmaku_src'
    filepattern: str = '{src_dir}/{name}.{tag}.xml'
    _danmakus: Optional[List['Danmaku']] = None
    _filename: Optional[str] = None
    def name(self) -> str:
        raise NotImplementedError()
    def filename(self):
        if self._filename is None:
            self._filename = self.filepattern.format(src_dir=self.src_dir, name=self.name(), tag=self.tag)
        return self._filename

    def download(self) -> str:
        raise NotImplementedError()
    def process(self, file: TextIO) -> List['Danmaku']:
        raise NotImplementedError()
    def danmakus(self):
        if not self._danmakus:
            filename = self.download()
            if os.path.exists(filename):
                with filein(filename, errors='replace') as f:
                    self._danmakus = list(sorted(self.process(f)))
            else:
                logger.warning('弹幕 %s 下载失败，%s 保存失败', self.name(), filename)
                self._danmakus = []
        return self._danmakus

class MixDanmakuList(MixSourceSet):
    """混入单个字幕的弹幕源"""
    def name(self) -> str: ...
    def index(self) -> int: ...
    def sources(self) -> Collection[ass.line._Line]: ...
    def danmakus(self) -> List['Danmaku']: ...

class DanmakuType(Enum):
    TOP = 0
    BOTTOM = 1
    FLOW = 2
    FLOW_BACKWARD = 3
    BILIBILI = 4
    ACFUN = 5

@dataclass(order=True)
class Danmaku:
    timeline: float # 弹幕出现时间（秒）
    timestamp: int # 弹幕发布时间（毫秒）
    no: int # 弹幕序号
    comment: str # 弹幕内容
    pos: DanmakuType # 弹幕类型
    color: int # 弹幕颜色
    size: float # 弹幕大小（相对于标准尺寸）
    height: int # 弹幕行数（字符数）
    width: int # 弹幕宽度（字符数）

class DanmakuLine(ass.Dialogue, NeedResize, metaclass=MyMetaClass):
    actor = _Field("Actor", str, default="")
    resize_width: int
    resize_height: int
    def resize(self, width: int, height: int):
        self.resize_width = width
        self.resize_height = height


class StringPromise:
    tostring: Callable[[], str]
    def __init__(self, tostring: Callable[[], str]) -> None:
        self.tostring = tostring
    def __str__(self) -> str:
        return self.tostring()

def timedelta_to_ass(td: timedelta) -> str:
    r = int(td.total_seconds())

    r, secs = divmod(r, 60)
    hours, mins = divmod(r, 60)

    return f'{hours:.0f}:{mins:02.0f}:{secs:02.0f}.{td.microseconds // 10000:02}'


class DanmakuStyle(ass.Style, NeedResize, metaclass=MyMetaClass):
    resize_width: int
    resize_height: int
    scale: float
    def __init__(self, *args, type_name=None, **kwargs):
        super().__init__(self, *args, type_name=None, **kwargs)
        self.name = f'Danmaku2ASS_{random.randint(0, 0xffff):04x}'
        alpha = kwargs.pop('alpha', kwargs.pop('Alpha', 1))
        alpha = int(255*alpha)
        if alpha > 255:
            alpha = 255
        elif alpha < 0:
            alpha = 0
        else:
            alpha = 255
        alpha = 255 - alpha
        self.scale = kwargs.pop('fontsize_vertical', kwargs.pop('FontsizeVertical', 25/1080))
        self.fontsize = StringPromise(lambda: str(self.resize_height * self.scale))
        color = Color(255, 255, 255, alpha)
        self.primary_color = color
        self.secondary_color = color
        backcolor = Color(0, 0, 0, alpha)
        self.outline_color = backcolor
        self.back_color = backcolor
        self.outline = StringPromise(lambda: str(max(1, float(str(self.fontsize)) / 25.0)))
        self.shadow = 0
        self.alignment = 7
        self.margin_l = 0
        self.margin_r = 0
        self.margin_v = 0
        self.encoding = 1
    def resize(self, width: int, height: int):
        self.resize_width = width
        self.resize_height = height


def CalculateLength(s):
    return max(map(len, s.split('\n')))  # May not be accurate


def ProcessComments(comments: Iterable[Danmaku], rows, density, vertical_percent, fontface, alpha, duration_marquee, duration_still, **_) -> Iterable[ass.line._Line]:
    # density 致密程度，弹幕和弹幕+空隙的比例
    # vertical_percent 弹幕部分占屏幕的比例，下面部分给字幕留空
    # rows 将弹幕部分均分为rows行
    # 最终弹幕的高度就是 fontsize * height
    fontsize = 1 * density / rows / vertical_percent
    style = DanmakuStyle(Fontname=fontface, FontsizeVertical=fontsize, Alpha=alpha)
    yield style
    occupied_rows: dict[DanmakuType, list[float]] = {pos: [0] * rows for pos in DanmakuType}
    for i in comments:
        if isinstance(i.pos, DanmakuType):
            row = OccupyRow(occupied_rows, i, duration_marquee, duration_still)
            if row != -1:
                yield WriteComment(i, row, density, duration_marquee, duration_still, style)
            # else:
            #     if not reduced:
            #         row = FindAlternativeRow(rows, i, height, bottomReserved)
            #         MarkCommentRow(rows, i, row)
            #         yield WriteComment(i, row, width, height, bottomReserved, fontsize, duration_marquee, duration_still, styleid)
        else:
            logger.warning('Invalid comment pos: %r with content: %r', i.pos, i.comment)


def OccupyRow(rows: dict[DanmakuType, list[float]], c: Danmaku, duration_marquee, duration_still):
    row = 0
    for row, occupied in enumerate(rows[c.pos]):
        if occupied < c.timeline:
            break
    else:
        return -1
    if c.pos in (DanmakuType.BOTTOM, DanmakuType.TOP):
        rows[c.pos][row] = c.timeline + duration_still
    else:
        rows[c.pos][row] = c.timeline + duration_marquee # * c.width * 480/848/36
    return row


def ASSEscape(s):
    def ReplaceLeadingSpace(s):
        sstrip = s.strip(' ')
        slen = len(s)
        if slen == len(sstrip):
            return s
        else:
            llen = slen - len(s.lstrip(' '))
            rlen = slen - len(s.rstrip(' '))
            return ''.join(('\u2007' * llen, sstrip, '\u2007' * rlen))
    return '\\N'.join((ReplaceLeadingSpace(i) or ' ' for i in str(s).replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}').split('\n')))


def WriteComment(c: Danmaku, row, density, duration_marquee, duration_still, style: DanmakuStyle):
    dialogue = DanmakuLine(Layer=2, Start=timedelta(seconds=c.timeline), Style=style.name)
    text = ASSEscape(c.comment)
    styles = []
    if c.pos == DanmakuType.TOP:
        styles.append(StringPromise(lambda: f'\\an8\\pos({dialogue.resize_width / 2}d, {style.resize_height * style.scale / density * (row + (1-density)/2)}d)'))
        duration = duration_still
    elif c.pos == DanmakuType.BOTTOM:
        styles.append(StringPromise(lambda: f'\\an2\\pos({dialogue.resize_width / 2}d, {style.resize_height * style.scale / density * (row + (1-density)/2)}d)'))
        duration = duration_still
    elif c.pos == DanmakuType.FLOW_BACKWARD:
        styles.append(StringPromise(lambda: f'\\move({style.resize_height * style.scale * -c.width}d, {style.resize_height * style.scale / density * (row + (1-density)/2)}d, {dialogue.resize_width}d, {style.resize_height * style.scale / density * (row + (1-density)/2)}d)'))
        duration = duration_marquee
    else:
        styles.append(StringPromise(lambda: f'\\move({dialogue.resize_width}d, {style.resize_height * style.scale / density * (row + (1-density)/2)}d, {style.resize_height * style.scale * -c.width}d, {style.resize_height * style.scale / density * (row + (1-density)/2)}d)'))
        duration = duration_marquee
    if abs(c.size - 1) > 1e-2:
        styles.append(f'\\fs{c.size-1:+.2f}')
    if c.color != 0xffffff:
        styles.append(f'\\c&H{c.color:06X}&')
        if c.color == 0x000000:
            styles.append('\\3c&HFFFFFF&')
    dialogue.text = StringPromise(lambda: '{' + ''.join(map(str, styles)) + '}' + text) # type: ignore
    dialogue.end = StringPromise(lambda: timedelta_to_ass(timedelta(seconds=c.timeline + duration))) # + duration * (c.width * style.resize_height * style.scale) / dialogue.resize_width )))
    return dialogue


def FindAlternativeRow(rows: list[list[Optional[Danmaku]]], c: Danmaku, height, bottomReserved):
    res = 0
    restimeline = float('inf')
    assert type(c.pos) is int
    for row in range(height - bottomReserved - math.ceil(c.height)):
        commentrow = rows[c.pos][row]
        if commentrow is None:
            return row
        elif commentrow.timeline < restimeline:
            res = row
            restimeline = commentrow.timeline
    return res


def parsecomments(src: Iterable[Danmaku], **kwargs) -> Iterable[ass.line._Line]:
    kwargs.update(LocalStorage()['style'])
    return ProcessComments(src, **kwargs)
