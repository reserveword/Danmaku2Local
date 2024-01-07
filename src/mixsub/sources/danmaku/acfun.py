
from dataclasses import dataclass
import json
import os
import re
import time
from typing import Iterable, TextIO

import requests

from mixsub.schema.models import MixSourceSeries
from mixsub.sources.danmaku import string_render_length, Danmaku, DanmakuList, DanmakuType
from mixsub.storage import fileout
from mixsub.util import logger, prefix

URL_AA = 'https://www.acfun.cn/bangumi/aa{aa}'
URL_AC = 'https://www.acfun.cn/v/ac{ac}'
URL_VID = 'https://www.acfun.cn/rest/pc-direct/new-danmaku/list'

session = requests.session()
session.headers['user-agent'] = 'myagent'

@dataclass
class AcfunDanmakuSeason(MixSourceSeries):
    aa: int

    def code(self):
        return 'aa' + str(self.aa)

    def expand(self):
        ''' 通过网站链接获取当前视频与整部番剧的信息（仅限番剧页）\n
        Args for example:
            aa123456789
        Credit: https://yleen.cc/archives/acfun-danmakus.html
        '''
        response = session.get(URL_AA.format(aa=self.aa))
        match_iter = re.finditer(r'window\.bangumiList = (\{.*\});\n', response.text)
        episodes = json.loads(next(match_iter).group(1)).get('items')
        return [AcfunDanmakuEpisode(i, e) for i, e in enumerate(episodes)]


@dataclass
class AcfunDanmakuEpisode(DanmakuList):
    # AcfunXmlMeta(cid=e['videoId'], bias=i, index=e['episodeName'], title=e['title'], full=e)
    filepattern: str = '{src_dir}/vid{name}.{tag}.xml'

    def code(self):
        return self.val['videoId']

    def index(self):
        return self.idx

    def download(self) -> str:
        filename = self.filename()
        vid(self.code(), filename)
        return filename

    def process(self, file: TextIO) -> list[Danmaku]:
        return list(read_comments_acfun(file))


@dataclass
class AcfunDanmakuVideo(MixSourceSeries):
    ac: int

    def code(self):
        return 'ac' + str(self.ac)

    def expand(self):
        ''' 通过网站链接获取当前视频与整部番剧的信息（仅限番剧页）\n
        Args for example:
            ac123456789
        Credit: https://yleen.cc/archives/acfun-danmakus.html
        '''
        response = session.get(URL_AC.format(ac=self.ac))
        match_iter = re.finditer(r'window\.videoInfo = (\{.*\});\n', response.text)
        parts = json.loads(next(match_iter).group(1)).get('video_list')
        return [AcfunDanmakuPart(i, e) for i, e in enumerate(parts)]


@dataclass
class AcfunDanmakuPart(DanmakuList):
    # AcfunXmlMeta(cid=int(e['id']), bias=i, index=e['fileName'], title=e['title'], full=e)
    filepattern: str = '{src_dir}/vid{name}.{tag}.xml'

    def code(self):
        return self.val['id']

    def index(self):
        return self.idx

    def download(self) -> str:
        filename = self.filename()
        vid(self.code(), filename)
        return filename

    def process(self, file: TextIO) -> list[Danmaku]:
        return list(read_comments_acfun(file))


@prefix('aa', on=True)
def aa(aacode: str) -> AcfunDanmakuSeason:
    return AcfunDanmakuSeason(int(aacode))

@prefix('ac', on=True)
def ac(accode: str) -> AcfunDanmakuSeason:
    return AcfunDanmakuSeason(int(accode))


@prefix('vid', on=False)
def vid(vidcode: str, name: os.PathLike | str) -> None:
    '''爬取番剧每集的弹幕存储为文件。\n
    Args:
        vidcode (String): resourceId
        name (String): 存放的文件路径
    '''
    try:
        # 单个弹幕文件的路径
        with fileout(name, 'x') as file:
            pcursor = 1 # 页码
            danmakus = [] # 用于输出结果的弹幕列表
            while True:
                response = session.post(
                    'https://www.acfun.cn/rest/pc-direct/new-danmaku/list', 
                    data={
                        'resourceId': vidcode,
                        'resourceType': 9,
                        'enableAdvanced': True,
                        'pcursor': pcursor,
                        'count': 200,
                        'sortType': 2,
                        'asc': True,
                    },
                ).json()
                # 往弹幕列表里追加本次获取到的弹幕
                danmakus.extend(response['danmakus'])
                if response['pcursor'] == 'no_more':
                    # 没有下一页了，就跳出循环
                    break
                pcursor += 1 # 下一页
                time.sleep(.1)
            json.dump({'content':danmakus}, file, ensure_ascii=False)
    except FileExistsError as e:
        logger.debug(e)
    except Exception as e:
        logger.warning(e)
        os.remove(name)
        raise


def read_comments_acfun(f) -> Iterable[Danmaku]:
    # {
    #     "likeCount": 0,
    #     "size": 25,
    #     "color": 16777215,
    #     "danmakuId": 213036230,
    #     "danmakuType": 0,
    #     "mode": 1,
    #     "roleId": 0,
    #     "danmakuStyle": 1,
    #     "danmakuAvatarUrl": "",
    #     "isLike": false,
    #     "danmakuImgUrl": "",
    #     "createTime": 1627401902387,
    #     "rank": 5,
    #     "userId": 56023767,
    #     "position": 3953, # ms
    #     "body": "来了来了"
    # },
    comments = json.load(f)['content']
    style_map = [DanmakuType.FLOW, DanmakuType.FLOW, DanmakuType.FLOW, DanmakuType.FLOW, DanmakuType.BOTTOM, DanmakuType.TOP]
    for i, comment in enumerate(comments):
        try:
            size = comment['size'] / 25.0
            c = str(comment['body']).replace('\\r', '\n').replace('\r', '\n')
            yield Danmaku(float(comment['position']) / 1000, int(comment['createTime']), i, c, style_map[comment['danmakuStyle']], int(comment['color']), size, (c.count('\n') + 1), string_render_length(c))
        except (AssertionError, AttributeError, IndexError, TypeError, ValueError):
            logger.warning('Invalid comment: %r', comment)
            continue
