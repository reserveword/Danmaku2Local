
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
import math
import os
import random
from typing import Iterable, Optional, TextIO

import ass
from ass.data import Color

from mixsub.schema.models import MixSourceSet, Renderer
from mixsub.storage import LocalStorage, filein
from mixsub.util import logger

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


@dataclass
class DanmakuList(MixSourceSet[Danmaku], metaclass=ABCMeta):
    idx: int
    val: dict
    tag: str = 'danmaku'
    src_dir: str = 'danmaku_src'
    filepattern: str = '{src_dir}/{name}.{tag}.xml'
    _danmakus: Optional[list['Danmaku']] = None
    _filename: Optional[str] = None
    def filename(self):
        if self._filename is None:
            self._filename = self.filepattern.format(src_dir=self.src_dir, name=self.code(), tag=self.tag)
        return self._filename

    @abstractmethod
    def download(self) -> str:
        """下载内容，返回文件绝对路径"""
    @abstractmethod
    def process(self, file: TextIO) -> list[Danmaku]:
        """解析下载结果"""
    def sources(self):
        if not self._danmakus:
            filename = self.download()
            if os.path.exists(filename):
                with filein(filename, errors='replace') as f:
                    self._danmakus = list(sorted(self.process(f)))
            else:
                logger.warning('弹幕 %s 下载失败，%s 保存失败', self.code(), filename)
                self._danmakus = []
        return self._danmakus


def danmaku_style(
    height: int,
    opaque: int=255,
    fontscale: float=25/1080,
    outline: float=1/25, # 以上是重定义的参数
    shadow: float=0, # 以下都是原版参数
    alignment: int=7,
    margin_l: int=0,
    margin_r: int=0,
    margin_v: int=0,
    **kwargs
) -> ass.Style:
    alpha=255-opaque
    white = Color(255, 255, 255, alpha)
    black = Color(0, 0, 0, alpha)
    return ass.Style(
        name=f'Danmaku2ASS_{random.randint(0, 0xffff):04x}',
        alpha=alpha,
        fontsize=height * fontscale,
        primary_color=white,
        secondary_color=white,
        outline_color=black,
        back_color=black,
        outline=max(1, height * fontscale * outline),
        shadow=shadow,
        alignment=alignment,
        margin_l=margin_l,
        margin_r=margin_r,
        margin_v=margin_v,
        **kwargs
    )


def string_render_length(s):
    return max(map(len, s.split('\n')))  # May not be accurate


def occupy_row(rows: dict[DanmakuType, list[float]], c: Danmaku, duration_marquee, duration_still):
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


def ass_escape(s):
    def replace_leading_space(s):
        sstrip = s.strip(' ')
        slen = len(s)
        if slen == len(sstrip):
            return s
        else:
            llen = slen - len(s.lstrip(' '))
            rlen = slen - len(s.rstrip(' '))
            return ''.join(('\u2007' * llen, sstrip, '\u2007' * rlen))
    return '\\N'.join((replace_leading_space(i) or ' ' for i in str(s).replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}').split('\n')))


def write_danmaku(c: Danmaku, row, width, height, scale, density, duration_marquee, duration_still, style_name: str):
    dialogue = ass.Dialogue(Layer=2, Start=timedelta(seconds=c.timeline), Style=style_name)
    text = ass_escape(c.comment)
    styles = []
    if c.pos == DanmakuType.TOP:
        styles.append(f'\\an8\\pos({width / 2}d, {height * scale / density * (row + (1-density)/2)}d)')
        duration = duration_still
    elif c.pos == DanmakuType.BOTTOM:
        styles.append(f'\\an2\\pos({width / 2}d, {height * scale / density * (row + (1-density)/2)}d)')
        duration = duration_still
    elif c.pos == DanmakuType.FLOW_BACKWARD:
        styles.append(f'\\move({height * scale * -c.width}d, {height * scale / density * (row + (1-density)/2)}d, {width}d, {height * scale / density * (row + (1-density)/2)}d)')
        duration = duration_marquee
    else:
        styles.append(f'\\move({width}d, {height * scale / density * (row + (1-density)/2)}d, {height * scale * -c.width}d, {height * scale / density * (row + (1-density)/2)}d)')
        duration = duration_marquee
    if abs(c.size - 1) > 1e-2:
        styles.append(f'\\fs{c.size-1:+.2f}')
    if c.color != 0xffffff:
        styles.append(f'\\c&H{c.color:06X}&')
        if c.color == 0x000000:
            styles.append('\\3c&HFFFFFF&')
    dialogue.text = '{' + ''.join(map(str, styles)) + '}' + text
    dialogue.end = timedelta(seconds=c.timeline + duration) # + duration * (c.width * style.resize_height * style.scale) / dialogue.resize_width )
    return dialogue


def find_alternative_row(rows: list[list[Optional[Danmaku]]], c: Danmaku, height, bottom_reserved):
    res = 0
    restimeline = float('inf')
    assert isinstance(c.pos, int)
    for row in range(height - bottom_reserved - math.ceil(c.height)):
        commentrow = rows[c.pos][row]
        if commentrow is None:
            return row
        elif commentrow.timeline < restimeline:
            res = row
            restimeline = commentrow.timeline
    return res


class DanmakuRenderer(Renderer[Danmaku]):
    def __init__(self, **kwargs):
        self.style = LocalStorage()['style']
        self.style.update(kwargs)
    def render(self, mixes: Iterable[Danmaku], doc: Optional[ass.Document]=None) -> ass.Document:
        if doc is None:
            doc = ass.Document()
            doc.play_res_x = 1920
            doc.play_res_y = 1080
        try:
            width, height = doc.play_res_x, doc.play_res_y
        except KeyError:
            width, height = 1920, 1080
        # density 致密程度，弹幕和弹幕+空隙的比例
        # covered_rate 弹幕部分占屏幕的比例，下面部分给字幕留空
        # rows 将弹幕部分均分为rows行
        # 最终弹幕的高度就是 fontscale * height
        density = self.style['density']
        fontscale = 1 * density / self.style['rows'] / self.style['covered_rate']
        style = danmaku_style(height, fontface=self.style['fontface'], fontscale=fontscale, opaque=self.style['opaque'])
        doc.styles.append(style)
        occupied_rows: dict[DanmakuType, list[float]] = {pos: [0] * self.style['rows'] for pos in DanmakuType}
        for i in mixes:
            if not isinstance(i.pos, DanmakuType):
                logger.warning('Invalid comment pos: %r with content: %r', i.pos, i.comment)
                continue
            else:
                duration_marquee = self.style['duration_marquee']
                duration_still = self.style['duration_still']
                row = occupy_row(occupied_rows, i, duration_marquee, duration_still)
                if row == -1:
                    logger.warning('Too many comments: %r', i)
                    # if not reduced:
                    #     row = find_alternative_row(rows, i, height, bottomReserved)
                    #     MarkCommentRow(rows, i, row)
                    #     yield write_danmaku(i, row, width, height, bottomReserved, fontsize, duration_marquee, duration_still, styleid)
                    continue
                else:
                    line = write_danmaku(i, row, width, height, fontscale, density, duration_marquee, duration_still, style.name) # type: ignore # style.name是类似属性property的机制
                    doc.events.append(line)
        return doc
