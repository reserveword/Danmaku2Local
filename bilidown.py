#! python3
# GPL v3.0+
# reserveword

import argparse
from collections import Counter, defaultdict
import functools
from io import StringIO, TextIOWrapper
import pickle
import sys
from typing import IO, Callable, MutableSequence, ParamSpecArgs, ParamSpecKwargs, Sequence, Tuple, TypeVar
import requests
import lxml.html as html
import re
import os
import random
import cv2
import ass

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
danmaku_ext = {'.xml', '.json', '.protobuf'}

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


def loadconfig() -> dict:
    try:
        with open(os.path.join(sys.path[0], 'bilidown.pickle'), 'rb') as cfg:
            return pickle.load(cfg)
    except:
        return {}


def saveconfig(cfg):
    try:
        with open(os.path.join(sys.path[0], 'bilidown.pickle'), 'wb') as cfgfile:
            pickle.dump(cfg, cfgfile)
    except:
        pass


def danmaku2ass(*args, joined_ass=None, **kwargs):
    kwargs.setdefault('stage_width', kwargs.pop('width', None))
    kwargs.setdefault('stage_height', kwargs.pop('height', None))
    if joined_ass == None:
        return Danmaku2ASS(*args, **kwargs)
    if type(joined_ass) == bytes:
        joined_ass = joined_ass.decode()
    if type(joined_ass) == str:
        with open(joined_ass, 'r') as file:
            return danmaku2ass(*args, joined_ass=ass.parse_file(joined_ass), **kwargs)
    if isinstance(joined_ass, IO[str]):
        return danmaku2ass(*args, joined_ass=ass.parse_file(joined_ass), **kwargs)
    if isinstance(joined_ass, IO[bytes]):
        return danmaku2ass(*args, joined_ass=ass.parse_file(TextIOWrapper(joined_ass)), **kwargs)
    if isinstance(joined_ass, ass.Document):
        danmaku_ass = StringIO()
        danmaku_ass_path = None
        if len(args) >= 3:
            danmaku_ass_path, args[2] = args[2], danmaku_ass
        else:
            danmaku_ass_path, kwargs['output_file'] = kwargs['output_file'], danmaku_ass
        Danmaku2ASS(*args, **kwargs)
        danmaku_ass = ass.parse_file(danmaku_ass)
        joined_ass.styles._lines += danmaku_ass.styles._lines
        joined_ass.events._lines += danmaku_ass.events._lines
        with open(danmaku_ass_path, 'w') as f:
            joined_ass.dump_file(f)


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
def get_cid(cid, full=False, name=None, width=1920, height=1080, *args, **kwargs):
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
            danmaku2ass(name, 'autodetect', os.path.splitext(
                name)[0] + '.ass', width, height, *args, **kwargs)
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


def fileclassify(ls, *clas, callback=None, **kwclas):
    for k, v in enumerate(clas):
        kwclas[k] = v
    rs = defaultdict(set)
    for file in ls:
        if os.path.isfile(file):
            base, ext = os.path.splitext(file)
            for k, v in kwclas.items():
                if ext in v:
                    rs[k].add(base)
                    if hasattr(callback, '__call__'):
                        callback(k, file=file, base=base, ext=ext)
    return rs


def video_get_resolution(file):
    cap = cv2.VideoCapture(file)
    return (cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT))


def match_local(remote, suffix='', *args, **kwargs):
    ls = os.listdir()
    resolution = []
    classify = fileclassify(ls, video_ext,
                            callback=lambda _, file, **_kw: resolution.append(video_get_resolution(file)))
    videos = classify[0]
    resolution = Counter(resolution).most_common(1)[0][0]
    kwargs['width'], kwargs['height'] = map(int, resolution)
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
    names_by_episode = [''.join(pattern)] + list(
        map(tuple.__getitem__, sorted(sorted(slot)[-1][1]), (1,)*len(videos)))
    print('各集名称：')
    print('\n'.join(names_by_episode[1:]))
    return get_any(remote, name_pattern=formattable(None, lambda *x, **k: names_by_episode[int(k['index'])] + suffix), *args, **kwargs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--local',
                        help='本地视频文件夹（默认为当前路径）', default=None)
    parser.add_argument('-r', '--remote',
                        help='b站ID（av/BV/ss/ep开头均可，网址也可以），留空代表读取本地弹幕文件', default=None)
    parser.add_argument('-t', '--tag',
                        help='字幕文件标签，用于区分弹幕和一般字幕。默认为.danmaku', default='.danmaku')
    parser.add_argument('--set-config', action='store_true',
                        help='保存本次设置为字幕的默认样式（只更新设置，不执行弹幕操作）')
    parser.add_argument('--reset-config', action='store_true',
                        help='删除已保存的字幕默认样式')
    parser.add_argument('-j', '--join-subtitle', metavar='TAG',
                        help='从以TAG结尾的文件读取字幕字幕并合并进弹幕中（需要ffmpeg，支持视频软内嵌字幕）')
    # args from Danmaku2ASS
    parser.add_argument('-s', '--size', metavar='WIDTHxHEIGHT',
                        help='Stage size in pixels', default=None)
    parser.add_argument('--font', metavar='FONT',
                        help='Specify font face [default: %s]' % '(FONT) sans-serif'[7:], default='(FONT) sans-serif'[7:])
    parser.add_argument('--fontsize', metavar='SIZE',
                        help=('Default font size [default: %s]' % 25), type=float, default=25.0)
    parser.add_argument('-a', '--alpha', metavar='ALPHA',
                        help='Text opacity', type=float, default=1.0)
    parser.add_argument('--duration-marquee', metavar='SECONDS',
                        help='Duration of scrolling comment display [default: %s]' % 5, type=float, default=5.0)
    parser.add_argument('--duration-still', metavar='SECONDS',
                        help='Duration of still comment display [default: %s]' % 5, type=float, default=5.0)
    parser.add_argument('-f', '--filter',
                        help='Regular expression to filter comments')
    parser.add_argument('--filter-file',
                        help='Regular expressions from file (one line one regex) to filter comments')
    parser.add_argument('-p', '--protect', metavar='HEIGHT',
                        help='Reserve blank on the bottom of the stage', type=int, default=0)
    parser.add_argument('--reduce', action='store_true',
                        help='Reduce the amount of comments if stage is full')
    # end of args from Danmaku2ASS
    args = parser.parse_args()
    try:
        width, height = str(args.size).split('x', 1)
        width = int(width)
        height = int(height)
    except ValueError:
        width = None
        height = None
    # 设置存储与重置
    cfg = loadconfig() if not args.reset_config else {}
    argcfg = {
        'width': width,
        'height': height,
        'reserve_blank': args.protect,
        'font_face': args.font,
        'font_size': args.fontsize,
        'text_opacity': args.alpha,
        'duration_marquee': args.duration_marquee,
        'duration_still': args.duration_still,
        'comment_filter': args.filter,
        'comment_filters_file': args.filter_file,
        'is_reduce_comments': args.reduce
    }
    for k, v in argcfg.items():
        if v != None:
            cfg[k] = v
    if args.set_config:
        saveconfig(cfg)
        exit(0)
    # 本地视频位置
    if args.local == None:
        args.local = input('请输入本地视频文件夹（默认为当前路径）：')
    if args.local:
        os.chdir(args.local)
    # 远程弹幕源位置
    if args.remote == None:
        args.remote = input('请输入b站ID（av/BV/ss/ep/md开头均可，网址也可以）：')
    # if args.tag == None:
    #     args.tag = input('请输入字幕文件标签，用于区分弹幕和一般字幕。默认为空：')
    if args.remote:
        print(match_local(
            args.remote,
            args.tag,
            **cfg
        ))
    else:
        ls = os.listdir()
        width = cfg.pop('width', None)
        height = cfg.pop('height', None)
        if width == None or height == None:
            resolution = [video_get_resolution(file) for file in ls
                          if os.path.splitext(file)[1] in video_ext]
            width, height = Counter(resolution).most_common(1)[0][0]
        danmakus = [(base, base+ext) for base, ext in [os.path.splitext(file) for file in ls]
                    if base.endswith(args.tag) and ext in danmaku_ext]
        for base, file in danmakus:
            danmaku2ass(
                file,
                'autodetect',
                base + '.ass',
                stage_width=int(width),
                stage_height=int(height),
                **cfg
            )
    if os.isatty(0):
        input('完成，按任意键关闭')
