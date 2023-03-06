#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

from io import StringIO
from ass import Document, parse_file
import functools
import lxml.html as html
import os
import re
import requests
from typing import Iterable, List, Optional, Sequence, overload

from d2l.danmaku2ass import Comment, GetCommentProcessor, ReadCommentsBilibili2, ProcessComments
from d2l.tagging import BiliXmlMeta
from d2l.storage import LocalStorage, filein, fileout
from d2l.logging import logger


url_av = 'https://api.bilibili.com/x/web-interface/view?aid={av}'
url_bv = 'https://api.bilibili.com/x/web-interface/view?bvid={bv}'
url_ss = 'https://bangumi.bilibili.com/view/web_api/season?season_id={ss}'
url_ep = 'https://www.bilibili.com/bangumi/play/{ep}'
url_md = 'https://api.bilibili.com/pgc/review/user?media_id={md}'
url_xml = 'https://api.bilibili.com/x/v1/dm/list.so?oid={oid}'



def prefix(prefix, on=True):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(key, *args, **kwargs):
            if type(key != str):
                key = str(key)
            if on:
                if not key.startswith(prefix):
                    key = prefix + str(key)
            else:
                if key.startswith(prefix):
                    key = key[len(prefix) :]
            return func(key, *args, **kwargs)

        return wrapper

    return decorator


def avbv(url) -> List[BiliXmlMeta]:
    url_json = requests.get(url).json()
    episodes = [
        BiliXmlMeta(cid=e['cid'], bias=i, index=str(e['page']), title=e['part'], full=e)
        for i, e in enumerate(url_json.get('data', {}).get('pages', []))
    ]
    return episodes


@prefix('av', on=False)
def av(av: str) -> List[BiliXmlMeta]:
    return avbv(url_av.format(av=av))


@prefix('BV', on=True)
def bv(bv: str) -> List[BiliXmlMeta]:
    return avbv(url_bv.format(bv=bv))


@prefix('ss', on=False)
def ss(ss: str) -> List[BiliXmlMeta]:
    ss_json = requests.get(url_ss.format(ss=ss)).json()
    episodes = [
        BiliXmlMeta(cid=e['cid'], bias=i, index=e['index'], title=e['title'], full=e)
        for i, e in enumerate(ss_json.get('result', {}).get('episodes', []))
    ]
    return episodes


@prefix('ep', on=True)
def ep(ep: str) -> List[BiliXmlMeta]:
    page = html.fromstring(requests.get(url_ep.format(ep=ep)).content)
    metas = page.xpath('/html/head/meta[@property="og:url"]')
    if len(metas):
        sscode = metas[0].get('content')
        sscode = next(re.finditer('ss[0-9]+', sscode))[0]
        return ss(sscode)
    raise RuntimeError('get episode failed')


@prefix('md', on=False)
def md(md: str) -> List[BiliXmlMeta]:
    md_json = requests.get(url_md.format(md=md)).json()
    ss = md_json['result']['media']['season_id']
    # print('season', ss)
    return ss(ss)


def code(code: str) -> List[BiliXmlMeta]:
    if code.startswith('ss'):
        return ss(code)
    elif code.startswith('av'):
        return av(code)
    elif code.startswith('BV'):
        return bv(code)
    elif code.startswith('ep'):
        return ep(code)
    elif code.startswith('md'):
        return md(code)
    raise RuntimeError('unknown code type')


# @prefix('cid', on=False)
def cid(cid: str | int, name: os.PathLike | str) -> None:
    try:
        with fileout(name, 'x') as file:
            with requests.get(url_xml.format(oid=cid), stream=True, timeout=1) as response:
                if response.status_code != 200:
                    logger.info(response.status_code, response.content.decode())
                    response.raise_for_status()
                    raise requests.HTTPError(f'返回HTTP代码{response.status_code}', response=response)
                for content in response.iter_content(None):
                    file.write(content)
    except FileExistsError as e:
        logger.warn(e)

def tocomments(name: os.PathLike | str, guess=False) -> Sequence[Comment]:
    with filein(name, errors='replace') as f:
        if guess:
            processor = GetCommentProcessor(f)
        else:
            processor = ReadCommentsBilibili2
        if processor is None:
            raise RuntimeError('弹幕类型未知')
        return list(sorted(processor(f, 1)))

def comments(_cid: str|int, name: os.PathLike | str) -> Sequence[Comment]:
    cid(_cid, name)
    return tocomments(name)

@overload
def parsecomments(src: Iterable[Comment], **kwargs) -> Document:...
@overload
def parsecomments(src: Iterable[Comment], name: str, **kwargs) -> None:...
def parsecomments(src: Iterable[Comment] | str, name: Optional[str]=None, **kwargs) -> Optional[Document]:
    if isinstance(src, str):
        src = tocomments(src)
    elif not isinstance(src, Sequence):
        src = list(src)
    style:dict = dict(LocalStorage()['style'])
    style.update(kwargs)
    scale = style['height'] / 1080.0
    style['fontsize'] *= scale
    style['bottomReserved'] = int(style['bottomReserved'] * scale)
    siz = style['fontsize']
    src = [Comment(s.timeline, s.timestamp, s.no, s.comment, s.pos, s.color, siz, s.height / s.size * siz, s.width / s.size * siz) for s in src]
    if name is None:
        sio = StringIO()
        ProcessComments(src, sio, **style)
        sio.seek(0)
        return parse_file(sio)
    else:
        ProcessComments(src, name, **style)
