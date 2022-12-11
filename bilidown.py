#! python3
# GPL v3.0+
# reserveword

import argparse
from collections import Counter, defaultdict
import datetime
import functools
from io import BytesIO, FileIO, StringIO, TextIOWrapper
import pickle
import shutil
from subprocess import PIPE, Popen
import sys
from typing import (
    Any,
    BinaryIO,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    MutableSequence,
    ParamSpecArgs,
    ParamSpecKwargs,
    Sequence,
    TextIO,
    Tuple,
    TypeVar,
)
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

video_ext = {
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
subtitle_ext = {'.ass', '.srt', '.smi', '.ssa', '.sub', '.stl', '.idx'}
danmaku_ext = {'.xml', '.json', '.protobuf'}
subtitle_guess = list(
    enumerate(
        [
            'default',
            'ch',
            'chn',
            'chinese',
            'zh',
            '中文',
            'sc',
            'SC',
            'simplified chinese',
            'zh_hans',
            'zh_cn',
            'zh_CN',
            '简体',
            '简中',
            '简体中文',
        ]
    )
)

_T = TypeVar('_T')


def lcs(a: MutableSequence[_T], b: MutableSequence[_T]) -> Tuple[MutableSequence[_T]]:
    result = [(0, (a[:0],)) for _ in a]
    for elem in b:
        last = (0, (b[:0],))
        source: Tuple[int, Tuple[MutableSequence[_T]]] = (0, (b[:0],))
        for i in range(len(a)):
            if elem == a[i]:
                source = (source[0] + 1, (*source[1][:-1], source[1][-1] + elem))
                # source[0] += 1
                # source[1][-1] += elem
            last = max(last, source, result[i])
            if last != source and len(last[1][-1]):
                last = (last[0], (*last[1], a[:0]))
            source, result[i] = result[i], last
    return max(result)[1]


class formattable:
    def __init__(
        self, base, formatter: Callable[[ParamSpecArgs, ParamSpecKwargs], str] = None
    ) -> None:
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


class Pairing:
    def __init__(self, mapper: Callable[[int], int], initial=1) -> None:
        self.mapper = mapper
        self.cache = []
        self.initial = initial
        self.head = initial

    def push(self, items: Iterable) -> Callable[[int], Any]:
        self.cache.extend(items)

        def pairer(index: int):
            idx = self.mapper(index + self.head) - self.head
            if idx < 0 or idx >= len(self.cache):
                return None
            else:
                return self.cache[idx]

        return pairer

    def __getitem__(self, index: int):
        idx = self.mapper(index + self.initial) - self.initial
        if idx < 0 or idx >= len(self.cache):
            return None
        else:
            return self.cache[idx]


def list_mapping(li: List[int], default=None):
    li.insert(0, 0)

    def mapper(id: int):
        if id < len(li):
            return li[id]
        else:
            return id if default is None else default

    return mapper


def dict_mapping(di: Dict[int, int], default=None):
    def mapper(id: int):
        if id in di:
            return di[id]
        else:
            return id if default is None else default

    return mapper


def lambda_mapping(l: str):
    return lambda x: eval(l, {'x': x})


def loadconfig() -> dict:
    try:
        with open(os.path.join(sys.path[0], 'bilidown.pickle'), 'rb') as cfg:
            return pickle.load(cfg)
    except:
        return {}


def saveconfig(cfg):
    print(os.path.join(sys.path[0], 'bilidown.pickle'))
    with open(os.path.join(sys.path[0], 'bilidown.pickle'), 'wb') as cfgfile:
        pickle.dump(cfg, cfgfile)


def get_id_extra(x: str):
    idhead = 0
    idtail = 0
    for i in x:
        if i.isdecimal():
            idtail += 1
        elif idtail == 0:
            idhead += 1
            idtail += 1
        else:
            break
    try:
        r = int(x[idhead:idtail])
        head = x[:idhead]
        tail = x[idtail:]
        extra = head + tail
        return r, extra
    except ValueError:
        return 0, x


def matching_sorter(items, sorter='sort'):
    if sorter == 'sort':
        return [ib + ie for (ib, ie) in sorted(items)]
    elif sorter == 'shuffle':

        def sortfunc(x):
            i, e = get_id_extra(x)
            return (e, i, x)

        return [ib + ie for (ib, ie) in sorted(items, key=sortfunc)]


def tostr(x):
    if type(x) == str:
        return x
    elif type(x) == bytes:
        return x.decode()
    elif type(x) == bytearray:
        return x.decode()
    else:
        return str(x)


def danmaku2ass(*args, joined_ass=None, shift=0, **kwargs):
    kwargs.setdefault('stage_width', kwargs.pop('width', None))
    kwargs.setdefault('stage_height', kwargs.pop('height', None))
    if joined_ass == None:
        kwargs.pop('join_encoding', 'utf-8')
        return Danmaku2ASS(*args, **kwargs)
    if type(joined_ass) == bytes:
        joined_ass = joined_ass.decode()
    if type(joined_ass) == str:
        encoding = kwargs.get('join_encoding', 'utf-8')
        with open(joined_ass, 'r', encoding=encoding) as file:
            return danmaku2ass(*args, joined_ass=ass.parse_file(file), shift=shift, **kwargs)
    if isinstance(joined_ass, (list, Generator, zip)):
        return danmaku2ass(
            *args, joined_ass=ass.parse_file(tostr(j) for j in joined_ass), shift=shift, **kwargs
        )
    if isinstance(joined_ass, TextIO):
        return danmaku2ass(*args, joined_ass=ass.parse_file(joined_ass), shift=shift, **kwargs)
    if isinstance(joined_ass, (BytesIO, BinaryIO, FileIO)):
        return danmaku2ass(
            *args, joined_ass=ass.parse_file(TextIOWrapper(joined_ass)), shift=shift, **kwargs
        )
    if isinstance(joined_ass, ass.Document):
        args = list(args)
        danmaku_ass = StringIO()
        danmaku_ass_path = None
        if len(args) >= 3:
            danmaku_ass_path, args[2] = args[2], danmaku_ass
        else:
            danmaku_ass_path, kwargs['output_file'] = kwargs['output_file'], danmaku_ass
        encoding = kwargs.pop('join_encoding', 'utf-8')
        if len(args) >= 4:
            args[3] = joined_ass.play_res_x
        else:
            kwargs['stage_width'] = joined_ass.play_res_x
        if len(args) >= 5:
            args[4] = joined_ass.play_res_y
        else:
            kwargs['stage_height'] = joined_ass.play_res_y
        Danmaku2ASS(*args, **kwargs)
        danmaku_ass.seek(0)
        danmaku_ass = ass.parse_file(danmaku_ass)
        if shift != 0:
            for event in danmaku_ass.events._lines:
                event.start += datetime.timedelta(seconds=shift)
                event.end += datetime.timedelta(seconds=shift)
        joined_ass.styles._lines += danmaku_ass.styles._lines
        joined_ass.events._lines += danmaku_ass.events._lines
        with open(danmaku_ass_path, 'w', encoding=encoding) as f:
            joined_ass.dump_file(f)


def fileclassify(ls, *clas, callback=None, **kwclas):
    for k, v in enumerate(clas):
        kwclas[k] = v
    rs = defaultdict(set)
    for file in ls:
        if os.path.isfile(file):
            base, ext = os.path.splitext(file)
            ext = ext.lower()
            for k, v in kwclas.items():
                if ext in v:
                    rs[k].add((base, ext))
                    if hasattr(callback, '__call__'):
                        callback(k, file=file, base=base, ext=ext)
    return rs


def video_get_resolution(file):
    cap = cv2.VideoCapture(file)
    return (cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT))


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


@prefix('av')
def get_av(av):
    pass


@prefix('BV')
def get_bv(bv):
    pass


@prefix('ss', on=False)
def get_ss(ss) -> List[Tuple[int, Dict[str, Any]]]:
    ss_json = requests.get(url_cid.format(ss=ss)).json()
    episodes = [
        {
            'cid': episode.get('cid'),
            'index': episode.get('index'),
        }
        for episode in ss_json.get('result', {}).get('episodes', {})
        if episode.get('episode_type') != -1 and episode.get('index').isdigit()
    ]
    # print list
    [
        print(
            season.get('season_id', {}),
            season.get('season_title', {}),
            season.get('title', {}),
        )
        for season in ss_json.get('result', {}).get('seasons', {})
    ]
    return [(episode['cid'], episode) for episode in episodes]


@prefix('cid', on=False)
def get_cid(cid, name=None, mode='xb') -> Tuple[str, str]:
    print(f'cid: {cid}, name: {name}')
    if name == None:
        name = cid + '.xml'
    elif not name.endswith('.xml'):
        name = name + '.xml'
    with requests.get(url_xml.format(oid=cid), stream=True, timeout=1) as response:
        if response.status_code != 200:
            print(response.status_code, response.content.decode())
            raise response
        try:
            with open(name, mode) as file:
                for content in response.iter_content(None):
                    file.write(content)
            # danmaku2ass(name, 'autodetect', os.path.splitext(
            #     name)[0] + '.ass', width, height, *args, **kwargs)
        except FileExistsError as e:
            print(e)
    return os.path.splitext(name)[0], '.xml'


@prefix('ep', on=True)
def get_ep(ep) -> str:
    page = html.fromstring(requests.get(url_ep.format(ep=ep)).content)
    metas = page.xpath('/html/head/meta[@property="og:url"]')
    if len(metas):
        ss = metas[0].get('content')
        print(ss)
        ss = next(re.finditer('ss[0-9]+', ss))[0]
        print(ss)
        return ss


@prefix('md', on=False)
def get_md(md) -> str:
    md_json = requests.get(url_md.format(md=md)).json()
    ss = md_json['result']['media']['season_id']
    print('season', ss)
    return ss


def get_local():
    ls = os.listdir()
    classify = fileclassify(ls, video_ext, subtitle_ext, danmaku_ext)
    videos = classify[0]
    subtitles = classify[1]
    danmakus = classify[2]
    return videos, subtitles, danmakus


def analysis_pattern_lcs(names, shuffle=False):
    # 用最长公共子序列猜测剧集使用的名称模式
    count_max = 1000
    if len(names) ** 2 - len(names) > count_max:
        matching = map(lcs, random.sample(combinations(names, 2), k=count_max))
    else:
        matching = (lcs(v1, v2) for v1 in names for v2 in names if v1 != v2)
    c = Counter(matching)
    # 为了避免'<something>0x<others>'占到大多数导致匹配结果为('<something>0', '<others>')
    # 将('<something>0', '<others>')也计入('<something>', '<others>')的数量
    # 计算方法为：只要A是B的子序列，就把B的数量计入A的数量
    # 结果以 出现次数*总字数*总字数/分段数 排序，取最高值
    pattern = (names[0],)
    patternval = 0
    for k, v in c.items():
        for k2, v2 in c.items():
            if k == k2:
                continue
            head = 0
            headhead = 0
            for p in k:
                while head < len(k2):
                    try:
                        headhead = k2[head].index(p, headhead) + len(p)
                        if headhead == len(k2[head]):
                            head += 1
                            headhead = 0
                        break
                    except:
                        head += 1
                        headhead = 0
                else:
                    break
            else:
                v += v2
        v = v * (sum(map(len, k)) ** 2) / len(k)
        if v > patternval:
            patternval = v
            pattern = k
    # pattern = c.most_common(1)[0][0]
    # 在最长公共子序列中断的地方查看，取数字最多的地方为集数字段
    # 如果最长公共子序列的最后不是原字符串的最后（即序列后还有一个字段），pattern结尾会有一个空字符串
    print(pattern)
    slot = [[0, []] for _ in pattern]
    for i in names:
        head = 0
        for j, k in enumerate(pattern):
            try:
                newhead = i.index(k, head)
            except ValueError:
                break
            valstr = i[head:newhead]
            valint, others = get_id_extra(valstr)
            slot[j][0] += valint
            slot[j][1].append((valint, others, i))
            head = newhead + len(k)
    # 将视频按照集数字段映射，弹幕就按照这个命名
    if shuffle:
        # 先按照非数字符号排序，没有非数字符号的按照整数排序
        def sorter(x):
            return (x[1], x[0], x[2])

    else:
        # 先按照整数排序，再按照原名排序
        def sorter(x):
            return (x[0], x[2])

    names_by_episode = [name for _, _, name in sorted(sorted(slot)[-1][1], key=sorter)]
    print('各集名称：')
    print('\n'.join(names_by_episode))
    return names_by_episode


route = {
    'av': get_av,
    'bv': get_bv,
    'BV': get_bv,
    'ss': get_ss,
    'ep': get_ep,
    'md': get_md,
    'cid': get_cid,
    'xml': Danmaku2ASS,
}


nextroute = {
    'ep': 'ss',
    'md': 'ss',
    'ss': 'cid',
    'cid': 'join',
    'join': 'xml',
}


def ffmpeg_get_subtitle(file):
    if os.name == 'nt':
        whereis = 'which'
    if os.name == 'posix':
        whereis = 'whereis'
    with Popen(whereis + ' ffmpeg', stdout=PIPE) as p:
        if not p.stdout.readline():
            print('ffmpeg not found!')
    with Popen(whereis + ' ffprobe', stdout=PIPE) as p:
        if not p.stdout.readline():
            print('ffprobe not found!')
    if ext in subtitle_ext:
        return Popen(
            [
                'ffmpeg',
                '-loglevel',
                'quiet',
                '-i',
                file,
                '-map',
                '0:s',
                '-f',
                'ass',
                '-',
            ],
            stdout=PIPE,
        ).stdout.readlines()
    with Popen(['ffprobe', '-i', file], stdout=PIPE) as p:
        cnt = -1
        subtitle_id = 0
        best_subtitle = 0
        best_guess = 0
        for line in p.stdout:
            if re.match(r'^ *Stream #0:[a-zA-Z0-9_()-]+: Subtitle:', line):
                subtitle_id += 1
                cnt = 5
            if cnt > 0:
                cnt -= 1
            else:
                continue
            for guess, keyword in subtitle_guess[best_guess:]:
                if keyword in line:
                    best_guess = guess
                    best_subtitle = subtitle_id
        return Popen(
            [
                'ffmpeg',
                '-loglevel',
                'quiet',
                '-i',
                file,
                '-map',
                '0:s:' + str(best_subtitle),
                '-f',
                'ass',
                '-',
            ],
            stdout=PIPE,
        ).stdout.readlines()


def get_any_cid(key, maxlen=None, mode='xb', *args, **kwargs):
    if key.startswith('ep'):
        state = 'ep'
    elif key.startswith('ss'):
        state = 'ss'
    elif key.startswith('av'):
        state = 'av'
    elif key.startswith('md'):
        state = 'md'
    # elif key.startswith('ep'):
    #     state = 'ep'
    else:
        parts = key.split('/')
        if len(parts) <= 1:
            return None
        for part in parts:
            try:
                ret = get_any_cid(part, maxlen, mode, *args, **kwargs)
                if ret != None:
                    return ret
            except:
                pass
        return None
    while state in ('av', 'bv', 'BV', 'ep', 'md', 'ss'):
        key = route[state](key)
        state = nextroute[state]
    if state == 'cid':
        if maxlen:
            key = key[:maxlen]
        key = [
            (get_cid(cid, name=f'{episode["index"]:>03}_{cid}', mode=mode), episode)
            for cid, episode in key
        ]
        return key


def get_danmaku_joined(
    dmks,
    names: Iterable[str],
    *args,
    joiner: Iterable[Tuple[List[bytes], str]] = None,
    shift=lambda x: 0,
    **kwargs,
):
    try:
        names = list(names)
        if joiner is None:
            joiner = [(None, None) for _ in names]
        for i, name, (joined, join_name) in zip(range(len(names)), names, joiner):
            if dmks[i] is not None:
                danmaku2ass(
                    dmks[i],
                    'autodetect',
                    name + '.ass',
                    *args,
                    joined_ass=joined,
                    shift=shift(i + 1),
                    **kwargs,
                )
            else:
                shutil.copy(join_name, name + '.ass')
    except Exception as e:
        for i in joiner:
            if hasattr(i, 'close'):
                try:
                    i.close()
                except:
                    pass
        raise e


if __name__ == '__main__':
    argcfg = {
        'tag': '.danmaku',
        'join_encoding': 'utf-8',
        'shuffle_branch': None,
        'font_face': '(FONT) sans-serif'[7:],
        'font_size': 25.0,
        'text_opacity': 1.0,
        'duration_marquee': 5.0,
        'duration_still': 5.0,
        'comment_filter': None,
        'comment_filters_file': None,
        'is_reduce_comments': None,
        'reserve_blank': 0,
    }
    cfg = dict(argcfg)
    cfg.update(loadconfig())
    parser = argparse.ArgumentParser()
    # fmt: off
    parser.add_argument('-l', '--local',
                        help='本地视频文件夹（默认为当前路径）')
    parser.add_argument('-r', '--remote', action='append',
                        help='b站ID（av/BV/ss/ep开头均可，网址也可以），留空代表读取本地弹幕文件')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='覆盖本地弹幕文件')
    parser.add_argument('-t', '--tag',
                        help='字幕文件标签，用于区分弹幕和一般字幕。默认为{tag}'.format(**cfg))
    parser.add_argument('--set-config', action='store_true',
                        help='更新字幕默认样式（只更新设置，不执行弹幕操作）')
    parser.add_argument('--reset-config', action='store_true',
                        help='重置字幕默认样式（同时以新设置同步弹幕）')
    parser.add_argument('-j', '--join', '--join-subtitle', metavar='TAG',
                        help='从以TAG结尾的文件读取字幕字幕并合并进弹幕中（需要ffmpeg，支持视频软内嵌字幕）')
    parser.add_argument('--join-sort', choices=['sort', 'shuffle'], default='sort',
                        help='字幕文件与视频匹配方法（sort=排序（默认）, shuffle=按--shuffle-branch排序）')
    parser.add_argument('--join-encoding', default='utf-8',
                        help='字幕文件编码，默认utf-8')
    parser.add_argument('--shuffle-branch', action='store_true',
                        help='让形如10.5集的集数放在最后，默认插在10集和11集之间')
    parser.add_argument('-m', '--mapping',
                        help='手动定义各集顺序，输入视频序号输出弹幕序号。'
                             '如 [1,3,2,4,5,6,7,8] 将二三集调换顺序、'
                             '{1:2,3:4} 将第二集弹幕映射到第一、二集视频上、'
                             '第四集弹幕映射到第三、四集视频上、'
                             'lambda x:x+1 将每一集弹幕映射到下一集视频上，'
                             '有多季弹幕时使用的是总集数')
    parser.add_argument('--shift',
                        help='调整各集弹幕相对时间，以秒计，正数会让弹幕延迟出现，如[5,4,3]会让前三集弹幕分别延迟5、4、3秒出现。'
                             '只有与现存字幕合并时才生效（注：当与mapping一同使用是集数指的是视频的集数）')
    # args from Danmaku2ASS
    parser.add_argument('-s', '--size', metavar='WIDTHxHEIGHT',
                        help='Stage size in pixels')
    parser.add_argument('--font', metavar='FONT',
                        help='Specify font face [default: {font_face}]'.format(**cfg))
    parser.add_argument('--fontsize', metavar='SIZE', type=float,
                        help='Default font size [default: {font_size}]'.format(**cfg))
    parser.add_argument('-a', '--alpha', metavar='ALPHA', type=float,
                        help='Text opacity')
    parser.add_argument('--duration-marquee', metavar='SECONDS', type=float,
                        help='Duration of scrolling comment display [default: {duration_marquee}]'.format(**cfg))
    parser.add_argument('--duration-still', metavar='SECONDS', type=float,
                        help='Duration of still comment display [default: {duration_still}]'.format(**cfg))
    parser.add_argument('-f', '--filter',
                        help='Regular expression to filter comments')
    parser.add_argument('--filter-file',
                        help='Regular expressions from file (one line one regex) to filter comments')
    parser.add_argument('-p', '--protect', metavar='HEIGHT', type=int,
                        help='Reserve blank on the bottom of the stage')
    parser.add_argument('--reduce', action='store_true',
                        help='Reduce the amount of comments if stage is full')
    # end of args from Danmaku2ASS
    # fmt: on
    args = parser.parse_args()
    # 解析集数映射关系
    if args.mapping:
        mapping = args.mapping
        if mapping[0] == '[':
            args.mapping = list_mapping([int(x) for x in mapping[1:-1].strip(',').split(',')])
        if mapping[0] == '{':
            args.mapping = dict_mapping(
                {
                    int(x.split(':')[0]): int(x.split(':')[1])
                    for x in mapping[1:-1].strip(',').split(',')
                }
            )
        if mapping.startswith('lambda x:'):
            args.mapping = lambda_mapping(mapping[9:])
    else:
        args.mapping = lambda x: x
    # 解析弹幕延迟映射关系
    if args.shift:
        shift = args.shift
        if shift[0] == '[':
            cfg['shift'] = list_mapping([int(x) for x in shift[1:-1].strip(',').split(',')], 0)
        if shift[0] == '{':
            cfg['shift'] = dict_mapping(
                {
                    int(x.split(':')[0]): int(x.split(':')[1])
                    for x in shift[1:-1].strip(',').split(',')
                },
                0,
            )
        if shift.startswith('lambda x:'):
            cfg['shift'] = lambda_mapping(shift[9:])
    # 设置分辨率
    try:
        width, height = str(args.size).split('x', 1)
        width = int(width)
        height = int(height)
    except ValueError:
        width = None
        height = None
    # 设置存储与重置
    if args.reset_config:
        cfg = dict(argcfg)
    cfg.update(
        (k, v)
        for k, v in {
            'tag': args.tag,
            'join_encoding': args.join_encoding,
            'shuffle_branch': args.shuffle_branch,
            'font_face': args.font,
            'font_size': args.fontsize,
            'text_opacity': args.alpha,
            'duration_marquee': args.duration_marquee,
            'duration_still': args.duration_still,
            'comment_filter': args.filter,
            'comment_filters_file': args.filter_file,
            'reserve_blank': args.protect,
            'is_reduce_comments': args.reduce,
        }.items()
        if v is not None
    )
    if args.set_config:
        print('setconfig')
        saveconfig(cfg)
        exit(0)
    tag = cfg.pop('tag')
    shuffle_branch = cfg.pop('shuffle_branch')
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
    videos, subtitles, danmakus = get_local()
    resolution = [video_get_resolution(b + e) for b, e in videos]
    resolution = Counter(resolution).most_common(1)[0][0]
    cfg['width'], cfg['height'] = map(int, resolution)
    if width != None and height != None:
        cfg.update(
            {
                'width': width,
                'height': height,
            }
        )
    # 附加字幕位置
    if args.join != None:
        base, ext = os.path.splitext(args.join)
        if not ext and base in video_ext:
            pool = matching_sorter(items=videos, sorter=args.join_sort)
        elif not ext and base in subtitle_ext:
            pool = matching_sorter(items=subtitles, sorter=args.join_sort)
        elif not ext or ext == '.':
            items = filter(lambda x: x[0].endswith(base), videos.union(subtitles))
            pool = matching_sorter(items=items, sorter=args.join_sort)
        else:
            items = filter(lambda x: x[0].endswith(base) and x[1] == ext, videos.union(subtitles))
            pool = matching_sorter(items=items, sorter=args.join_sort)
        cfg['joiner'] = ((ffmpeg_get_subtitle(item), item) for item in pool)
    danmaku_pool = Pairing(args.mapping)
    videos_base = [v for v, _ in videos]
    names_by_episode = analysis_pattern_lcs(videos_base)
    for remote in args.remote:
        if remote != '':
            dmks = get_any_cid(
                remote,
                mode=('xb' if not args.overwrite else 'wb'),
                **cfg,
            )
            danmaku_pool.push(base + ext for (base, ext), episode in dmks)
        else:
            danmaku_pool.push(base + ext for (base, ext) in sorted(danmakus))
    for i, j in enumerate(names_by_episode):
        print(danmaku_pool[i], j)
    get_danmaku_joined(danmaku_pool, (name + tag for name in names_by_episode), **cfg)
    if os.isatty(0):
        input('完成，按任意键关闭')
