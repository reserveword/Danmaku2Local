#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

from dataclasses import dataclass
import os
from typing import Iterable, List, Optional, TextIO
import xml.dom.minidom
import ass
import requests

from mixsub.sources.danmaku import CalculateLength, Danmaku, DanmakuList, DanmakuType, parsecomments
from mixsub.storage import fileout
from mixsub.util import MixSourceSeries, logger, prefix

url_av = 'https://api.bilibili.com/x/web-interface/view?aid={av}'
url_bv = 'https://api.bilibili.com/x/web-interface/view?bvid={bv}'
url_ss = 'https://api.bilibili.com/pgc/view/web/season?season_id={ss}'
url_ep = 'https://api.bilibili.com/pgc/view/web/season?ep_id={ep}'
url_md = 'https://api.bilibili.com/pgc/review/user?media_id={md}'
url_xml = 'https://api.bilibili.com/x/v1/dm/list.so?oid={oid}'
url_xml_2 = 'https://comment.bilibili.com/{oid}.xml'
url_av_biliplus = 'https://www.biliplus.com/api/view?id={av}'

session = requests.session()
session.headers['user-agent'] = 'myagent'


@dataclass
class BiliDanmakuSeason(MixSourceSeries):
    ss: int

    def name(self):
        return 'ss' + str(self.ss)

    def expand(self):
        ss_json = session.get(url_ss.format(ss=self.ss)).json()
        episodes = ss_json.get('result', {}).get('episodes', [])
        return [BiliDanmakuEpisode(i, e) for i, e in enumerate(episodes)]


@dataclass
class BiliDanmakuEpisode(DanmakuList):
    # BiliXmlMeta(cid=e['cid'], bias=i, index=e['index'], title=e['index_title'], full=e)
    filepattern: str = '{src_dir}/cid{name}.{tag}.xml'
    _sources: Optional[List[ass.line._Line]] = None

    def name(self):
        return self.val['cid']

    def index(self):
        return self.idx

    def download(self) -> str:
        filename = self.filename()
        cid(self.name(), filename)
        return filename

    def process(self, file: TextIO) -> List[Danmaku]:
        return list(ReadCommentsBilibili(file))

    def sources(self):
        if self._sources is None:
            self._sources = list(parsecomments(self.danmakus()))
        return self._sources



@dataclass
class BiliDanmakuAv(MixSourceSeries):
    av: int

    def name(self):
        return 'av' + str(self.av)

    def expand(self):
        av_json = session.get(url_av.format(av=self.av)).json()
        parts = av_json.get('data', {}).get('pages', [])
        if not parts:
            # 用biliplus api
            logger.warning('av信息已失效，使用biliplus API')
            av_json = session.get(url_av_biliplus.format(av=av)).json()
            parts = av_json.get('list', [])
        return [BiliDanmakuPart(i, e) for i, e in enumerate(parts)]


@dataclass
class BiliDanmakuBv(MixSourceSeries):
    bv: str

    def name(self):
        return self.bv

    def expand(self):
        bv_json = session.get(url_bv.format(bv=self.bv)).json()
        parts = bv_json.get('data', {}).get('pages', [])
        return [BiliDanmakuPart(i, e) for i, e in enumerate(parts)]


@dataclass
class BiliDanmakuPart(DanmakuList):
    # BiliXmlMeta(cid=e['cid'], bias=i, index=str(e['page']), title=e['part'], full=e)
    filepattern: str = '{src_dir}/cid{name}.{tag}.xml'
    _sources: Optional[List[ass.line._Line]] = None

    def name(self):
        return self.val['cid']

    def index(self):
        return self.idx

    def download(self) -> str:
        filename = self.filename()
        cid(self.name(), filename)
        return filename

    def process(self, file: TextIO) -> List[Danmaku]:
        return list(ReadCommentsBilibili(file))

    def sources(self):
        if self._sources is None:
            self._sources = list(parsecomments(self.danmakus()))
        return self._sources


@prefix('av', on=False)
def av(avcode: str) -> BiliDanmakuAv:
    return BiliDanmakuAv(int(avcode))


@prefix('bv', on=True)
def bv(bvcode: str) -> BiliDanmakuBv:
    return BiliDanmakuBv(bvcode)


@prefix('ss', on=False)
def ss(sscode: str) -> BiliDanmakuSeason:
    return BiliDanmakuSeason(int(sscode))


@prefix('ep', on=False)
def ep(epcode: str) -> BiliDanmakuSeason:
    ep_json = session.get(url_ep.format(ep=epcode)).json()
    sscode = ep_json['result']['season_id']
    return ss(sscode)


@prefix('md', on=False)
def md(mdcode: str) -> BiliDanmakuSeason:
    md_json = session.get(url_md.format(md=mdcode)).json()
    sscode = md_json['result']['media']['season_id']
    return ss(sscode)


@prefix('cid', on=False)
def cid(cidcode: str, name: os.PathLike | str) -> None:
    try:
        with fileout(name, 'xb') as file:
            if cidcode == '0':
                file.write(b'<?xml version="1.0" encoding="UTF-8"?><i></i>')
                return
            with session.get(url_xml.format(oid=cidcode), stream=True) as response:
                if response.status_code != 200:
                    logger.info(response.status_code)
                    logger.info(response.content.decode())
                    response.raise_for_status()
                    raise requests.HTTPError(
                        f'返回HTTP代码{response.status_code}', response=response
                    )
                for content in response.iter_content(None):
                    file.write(content)
    except FileExistsError as e:
        logger.debug(e)
    except Exception as e:
        logger.warning(e)
        os.remove(name)
        raise

BILI_DANKAKU_TYPE_MAP = {'1': DanmakuType.FLOW, '4': DanmakuType.BOTTOM, '5': DanmakuType.TOP, '6': DanmakuType.FLOW_BACKWARD}
def ReadCommentsBilibili(f) -> Iterable[Danmaku]:
    dom = xml.dom.minidom.parse(f)
    comment_element = dom.getElementsByTagName('d')
    for i, comment in enumerate(comment_element):
        try:
            timeline, dmktype, size, color, timestamp, *_ = str(comment.getAttribute('p')).split(',')
            assert dmktype in ('1', '4', '5', '6', '7', '8')
            if comment.childNodes.length > 0:
                if dmktype in ('1', '4', '5', '6'):
                    c = str(comment.childNodes[0].wholeText).replace('/n', '\n')
                    yield Danmaku(float(timeline), int(timestamp), i, c, BILI_DANKAKU_TYPE_MAP[dmktype], int(color), int(size)/25, (c.count('\n') + 1), CalculateLength(c))
                elif dmktype == '7':  # positioned comment
                    # c = str(comment.childNodes[0].wholeText)
                    # yield Danmaku(float(p[0]), int(p[4]), i, c, 'bilipos', int(p[3]), int(p[2]), 0, 0)
                    pass
                elif dmktype == '8':
                    pass  # ignore scripted comment
        except (AssertionError, AttributeError, IndexError, TypeError, ValueError):
            logger.warning('Invalid comment: %r', comment.toxml())
            continue
