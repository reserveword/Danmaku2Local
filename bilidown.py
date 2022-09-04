#! python3
# GPL v3.0+
# reserveword

import argparse
from collections import Counter
import functools
from typing import Callable, MutableSequence, ParamSpecArgs, ParamSpecKwargs, Sequence, Tuple, TypeVar
import requests
import lxml.html as html
import re
import os
import random
import cv2

from danmaku2ass import Danmaku2ASS

url_av = 'https://www.bilibili.com/video/{av}'
url_bv = 'https://www.bilibili.com/video/{bv}'
url_ss = 'https://www.bilibili.com/bangumi/play/{ss}'
url_ep = 'https://www.bilibili.com/bangumi/play/{ep}'
url_md = 'https://api.bilibili.com/pgc/review/user?media_id={md}'
url_cid = 'https://bangumi.bilibili.com/view/web_api/season?season_id={ss}'
url_xml = 'https://api.bilibili.com/x/v1/dm/list.so?oid={oid}'

video_ext = {'.mp4', '.m4v', '.mov', '.qt', '.avi', '.flv', '.wmv', '.asf', '.mpeg',
             '.mpg', '.vob', '.mkv', '.asf', '.wmv', '.rm', '.rmvb', '.vob', '.ts', '.dat'}
subtitle_ext = {'.ass', '.srt', '.smi', '.ssa', '.sub', '.stl', '.idx'}
# danmaku_ext = {'.xml', '.json', '.protobuf'}

_T = TypeVar('_T')


def lcs(a: MutableSequence[_T], b: MutableSequence[_T]) -> Tuple[MutableSequence[_T]]:
    result = [(0, (a[:0],)) for _ in a]
    for elem in b:
        last = (0, (b[:0],))
        source: Tuple[int, Tuple[MutableSequence[_T]]] = (0, (b[:0],))
        for i in range(len(a)):
            if elem == a[i]:
                source = (source[0] + 1, (*source[1]
                          [:-1], source[1][-1] + elem))
                # source[0] += 1
                # source[1][-1] += elem
            last = max(last, source, result[i])
            if last != source and len(last[1][-1]):
                last = (last[0], (*last[1], a[:0]))
            source, result[i] = result[i], last
    return max(result)[1]


class formattable:
    def __init__(self, base, formatter: Callable[[ParamSpecArgs, ParamSpecKwargs], str] = None) -> None:
        if formatter == None:
            self.format = base.format
        else:
            self.format = functools.partial(formatter, base)


class combinations(Sequence):
    def __init__(self, l: MutableSequence, r: int = 2):
        self.list = l
        self.length = len(l)

    def __getitem__(self, __i: int):
        if i < 0:
            i += len(self)
        if __i > len(self) or i < 0:
            raise IndexError()
        x = __i // self.length
        y = __i % self.length
        if x >= y:
            x += 1
        return (self.list[x], self.list[y])

    def __len__(self):
        return self.length * (self.length - 1)


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
                    key = key[len(prefix):]
            return func(key, *args, **kwargs)
        return wrapper
    return decorator


@prefix('av')
def get_av(av, full=False):
    pass


@prefix('BV')
def get_bv(bv, full=False):
    pass


@prefix('ss', on=False)
def get_ss(ss, full=False, name_pattern='ss{ss}[{index}]_ep{ep_id}', *args, **kwargs):
    ss_json = requests.get(url_cid.format(ss=ss)).json()
    episodes = [{
        'cid': episode.get('cid', 0),
        'ep_id': episode.get('ep_id', 0),
        'index': episode.get('index', 0),
    } for episode in ss_json.get('result', {}).get('episodes', {})
        if episode.get('episode_type') != -1
        and '精彩看点' not in episode.get('index_title', '')
        and episode.get('index').isdigit()
    ]
    [print(season.get('season_id', {}), season.get('season_title', {}), season.get(
        'title', {})) for season in ss_json.get('result', {}).get('seasons', {})]
    return [get_cid(episode['cid'], full, name_pattern.format(ss=ss, **episode), *args, **kwargs) for episode in episodes]


@prefix('cid', on=False)
def get_cid(cid, full=False, name=None, width=1920, height=1080):
    print('cid', cid)
    if name == None:
        name = cid + '.xml'
    elif not name.endswith('.xml'):
        name = name + '.xml'
    with requests.get(url_xml.format(oid=cid), stream=True, timeout=1) as response:
        if response.status_code != 200:
            print(response.status_code, response.content.decode())
        try:
            with open(name, 'xb') as file:
                for content in response.iter_content(None):
                    file.write(content)
            Danmaku2ASS(name, 'autodetect', os.path.splitext(
                name)[0] + '.ass', 1920, 1080)
        except FileExistsError as e:
            print(e)
    return name


@prefix('ep', on=True)
def get_ep(ep, full=False, *args, **kwargs):
    page = html.fromstring(requests.get(url_ep.format(ep=ep)).content)
    metas = page.xpath('/html/head/meta[@property="og:url"]')
    if len(metas):
        ss = metas[0].get('content')
        print(ss)
        ss = next(re.finditer('ss[0-9]+', ss))[0]
        print(ss)
        return get_ss(ss, full, *args, **kwargs)

@prefix('md', on=False)
def get_md(md, full=False, *args, **kwargs):
    md_json = requests.get(url_md.format(md=md)).json()
    ss = md_json['result']['media']['season_id']
    print('season', ss)
    return get_ss(ss)

def get_any(key, *args, **kwargs):
    if key.startswith('ep'):
        return get_ep(key, *args, **kwargs)
    elif key.startswith('ss'):
        return get_ss(key, *args, **kwargs)
    elif key.startswith('av'):
        return get_av(key, *args, **kwargs)
    elif key.startswith('md'):
        return get_md(key, *args, **kwargs)
    # elif key.startswith('ep'):
    #     return get_ep(key, *args, **kwargs)
    else:
        parts = key.split('/')
        if len(parts) <= 1:
            return None
        for part in parts:
            try:
                ret = get_any(part, *args, **kwargs)
                if ret != None:
                    return ret
            except:
                pass
        return None


def match_local(remote, local=None, suffix=''):
    if local:
        os.chdir(local)
    ls = os.listdir()
    videos = set()
    # subtitles = set()
    # danmakus = set()
    resolution = []
    for file in ls:
        if os.path.isfile(file):
            base, ext = os.path.splitext(file)
            if ext in video_ext:
                videos.add(base)
                cap = cv2.VideoCapture(file)
                resolution.append(
                    (cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            # elif ext in subtitle_ext:
            #     subtitles.add(base)
            # elif ext in danmaku_ext:
            #     danmakus.add(base)
    resolution = Counter(resolution).most_common(1)[0][0]
    # 用最长公共子序列猜测剧集使用的名称模式
    count_max = 1000
    if len(videos)**2 - len(videos) > count_max:
        matching = map(lcs, random.sample(
            combinations(videos, 2), k=count_max))
    else:
        matching = (lcs(v1, v2) for v1 in videos for v2 in videos if v1 != v2)
    c = Counter(matching)
    # 为了避免'<something>0x<others>'占到大多数导致匹配结果为('<something>0', '<others>')
    # 将('<something>0', '<others>')也计入('<something>', '<others>')的数量
    # 结果以 出现次数*总字数*总字数/分段数 排序，取最高值
    pattern = None
    patternval = 0
    for k, v in c.items():
        for k2, v2 in c.items():
            if k == k2:
                continue
            head = 0
            for p in k:
                for q in range(head, len(k2)):
                    head += 1
                    if p in k2[q]:
                        break
                else:
                    break
            else:
                v += v2
        v = v*(sum(map(len, k))**2)/len(k)
        if v > patternval:
            patternval = v
            pattern = k
    # pattern = c.most_common(1)[0][0]
    # 在最长公共子序列中断的地方查看，取数字最多的地方为集数字段
    # 如果最长公共子序列的最后不是原字符串的最后（即序列后还有一个字段），pattern结尾会有一个空字符串
    slot = [[0, []] for _ in pattern]
    for i in videos:
        head = 0
        for j, k in enumerate(pattern):
            try:
                newhead = i.index(k, head)
            except ValueError:
                break
            val = ''.join(filter('0123456789'.__contains__, i[head:newhead]))
            slot[j][0] += len(val)
            if val.isdigit():
                slot[j][1].append((int(val), i))
            head = newhead + len(k)
    # 将视频按照集数对应的整数排序，弹幕就按照这个命名
    names_by_episode = [''.join(
        pattern)] + list(map(tuple.__getitem__, sorted(slot)[-1][1], (1,)*len(videos)))
    print('各集名称：')
    print('\n'.join(names_by_episode[1:]))
    return get_any(remote, name_pattern=formattable(None, lambda *x, **k: names_by_episode[int(k['index'])] + suffix))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--local', help='本地视频文件夹（默认为当前路径）', default=None)
    parser.add_argument(
        '-r', '--remote', help='b站ID（av/BV/ss/ep开头均可，网址也可以）', default=None)
    parser.add_argument(
        '-s', '--suffix', help='字幕文件tag，用于区分弹幕和一般字幕。默认为空', default=None)
    args = parser.parse_args()
    if args.local == None:
        args.local = input('请输入本地视频文件夹（默认为当前路径）：')
    while not args.remote:
        args.remote = input('请输入b站ID（av/BV/ss/ep/md开头均可，网址也可以）：')
    if args.suffix == None:
        args.suffix = input('请输入字幕文件tag，用于区分弹幕和一般字幕。默认为空：')
    print(match_local(args.remote, args.local, args.suffix))
    if os.isatty():
        input('完成，按任意键关闭')
