#! /usr/bin/env python3
# -*- encoding:utf-8 -*-

import os
import argparse
import re

from d2l import *

gcfg = storage.GlobalStorage()
cfg = storage.LocalStorage()
parser = argparse.ArgumentParser()
style = cfg['style']
# 单字母参数：aeflprtv
# fmt: off
parser.add_argument('-l', '--local',
                    help='本地视频文件夹（默认为当前路径）')
parser.add_argument('-r', '--remote', action='append', default=[],
                    help='b站ID（av/BV/ss/ep开头均可，网址也可以），留空代表读取本地弹幕文件')
parser.add_argument('-e', '--episode', action='append', default=[],
                    help='只处理指定集数')
# parser.add_argument('-o', '--overwrite', action='store_true',
#                     help='覆盖本地弹幕文件')
parser.add_argument('-t', '--tag',
                    help='字幕文件标签，用于区分弹幕和一般字幕。默认为{tag}'.format(tag=cfg['tag']))
parser.add_argument('--set-config', action='store_true',
                    help='更新全局配置（只更新设置，不执行弹幕操作）')
parser.add_argument('-v', '--verbose', action='store_true',
                    help='显示详细日志')
parser.add_argument('--level',
                    help='日志等级')
# parser.add_argument('--reset-config', action='store_true',
#                     help='重置字幕默认样式（同时以新设置同步弹幕）')
# parser.add_argument('-j', '--join', '--join-subtitle', metavar='glob',
#                     help='从能匹配glob的文件读取字幕字幕并合并进弹幕中（需要ffmpeg，支持视频软内嵌字幕）')
# parser.add_argument('--sort', choices=['default', 'plain', 'front', 'middle', 'end', 'filename'],
#                     help='字幕文件与视频匹配方法（default=默认排序, plain=字典序, front=带前后缀的集数在最前面, middle=对应集中间, end=最后面, filename=字典序，但是连续的数字按整数排序）')
# parser.add_argument('--sort-sub', choices=['default', 'plain', 'front', 'middle', 'end', 'filename'],
#                     help='字幕文件与视频匹配方法（default=默认排序, plain=字典序, front=带前后缀的集数在最前面, middle=对应集中间, end=最后面）, filename=字典序，但是连续的数字按整数排序')
# parser.add_argument('--join-encoding', default='utf-8',
#                     help='字幕文件编码，默认utf-8')
# parser.add_argument('-m', '--mapping',
#                     help='手动定义各集顺序，输入视频序号输出弹幕序号。'
#                          '如 [1,3,2,4,5,6,7,8] 将二三集调换顺序、'
#                          '{1:2,3:4} 将第二集弹幕映射到第一、二集视频上、'
#                          '第四集弹幕映射到第三、四集视频上、'
#                          'lambda x:x+1 将每一集弹幕映射到下一集视频上，'
#                          '有多季弹幕时使用的是总集数')
parser.add_argument('--shift',
                    help='调整各集弹幕相对时间，以秒计，正数会让弹幕延迟出现，如[5,4,3]会让前三集弹幕分别延迟5、4、3秒出现。'
                            '只有与现存字幕合并时才生效（注：当与mapping一同使用是集数指的是视频的集数）')
parser.add_argument('--replay', action='store_true',
                    help='重新执行本目录下的上次命令')
parser.add_argument('--replay-global', action='store_true',
                    help='重新执行上次命令')
parser.add_argument('--reset', action='store_true',
                    help='清空本目录配置')
parser.add_argument('--reset-global', action='store_true',
                    help='清空全局配置')
parser.add_argument('--dump-local', action='store_true',
                    help='查看本地配置')
parser.add_argument('--no-cache', action='store_true',
                    help='忽略缓存结果')
# args from Danmaku2ASS
# parser.add_argument('-s', '--size', metavar='WIDTHxHEIGHT',
#                     help='Stage size in pixels')
parser.add_argument('--font', metavar='FONT',
                    help='Specify font face [default: {fontface}]'.format(**style))
parser.add_argument('--fontsize', metavar='SIZE', type=float,
                    help='Default font size relative to 1920*1080 [default: {fontsize}]'.format(**style))
parser.add_argument('-a', '--alpha', metavar='ALPHA', type=float,
                    help='Text opacity')
parser.add_argument('--duration-marquee', metavar='SECONDS', type=float,
                    help='Duration of scrolling comment display [default: {duration_marquee}]'.format(**style))
parser.add_argument('--duration-still', metavar='SECONDS', type=float,
                    help='Duration of still comment display [default: {duration_still}]'.format(**style))
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
# 日志等级
if isinstance(args.level, str) and args.level.upper() in ('DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'CRITICAL', 'FATAL'):
    logger.setLevel(args.level.upper())
elif args.verbose:
    logger.setLevel('DEBUG')
# 判断仅配置不运行的情况
no_exec = False
if args.reset_global:
    gcfg.clear()
    gcfg.dump()
    logger.info('已重置全局配置')
    no_exec = True
if args.reset:
    cfg.clear()
    cfg.dump()
    logger.info('已重置本地配置')
    no_exec = True
if args.dump_local:
    logger.critical(f'本地配置：{cfg}')
    no_exec = True
if no_exec:
    exit(0)
del no_exec
# 补完默认参数，判断全局配置的情况
stylenow = dict(style)
if args.filter:
    comment_filters = [args.filter]
else:
    comment_filters = []
if args.filter_file:
    with open(args.filter_file, 'r') as f:
        d = f.readlines()
        comment_filters.extend([i.strip() for i in d])
filters_regex = []
for comment_filter in comment_filters:
    try:
        if comment_filter:
            filters_regex.append(re.compile(comment_filter))
    except:
        raise ValueError('Invalid regular expression: %s' % comment_filter)
stylenow.update(
    (k, v)
    for k, v in {
        'bottomReserved': args.protect,
        'fontface': args.font,
        'fontsize': args.fontsize,
        'alpha': args.alpha,
        'duration_marquee': args.duration_marquee,
        'duration_still': args.duration_still,
        'filters_regex': (),
        'reduced': args.reduce,
        'progress_callback': None,
    }.items()
    if v is not None
)
if args.set_config:
    gcfg['style'] = stylenow
    if type(args.tag) is str and len(args.tag):
        gcfg['tag'] = args.tag
    gcfg.dump()
    exit(0)
else:
    cfg['style'] = stylenow
    if type(args.tag) is str and len(args.tag):
        cfg['tag'] = args.tag
    cfg.dump()

# 如果确定要运行，记下本次运行的参数
if args.replay:
    args = cfg['last-run']
    logger.info(f'running with local last run args: {args}')
elif args.replay_global:
    dir = gcfg['last-run-path']
    args = gcfg['last-run']
    logger.info(f'running with last run args: {args}, at dir: {dir}')
    os.chdir(dir)
    if args.local:
        os.chdir(args.local)
    cfg.load()
else:
    gcfg['last-run'] = args
    gcfg['last-run-path'] = os.path.abspath('.')
    gcfg.dump()
    # 如果有本地路径重定向，运行参数记载到重定向后的目录
    if args.local:
        os.chdir(args.local)
    cfg['last-run'] = args
    cfg.dump()

if args.no_cache:
    cfg.pop('seq-singular', None)
    cfg.pop('done', None)

# 运行
try:
    seq, singular = cfg['seq-singular']
    logger.info('发现自动探测结果缓存，剧集列表如下：')
except KeyError:
    dir = l.dir()
    v, s1 = l.l(dir[l.FileType.VIDEO])
    s2 = ass.ass(dir[l.FileType.SUBTITLE])
    d1 = []
    for c in args.remote:
        d1.extend(r.r(c))
    d2 = l.d(dir[l.FileType.DANMAKU])
    v, d, s = v, d2, s1+s2
    del s1,s2,d2
    # cfg['vds'] = (v,d,s)
    seq, singular = tagging.match(v, d, s)
    cfg['seq-singular'] = seq, singular
    logger.info('自动探测完成，剧集列表如下：')
for i, (vv, dd, ss) in enumerate(seq):
    logger.info(f'第{i+1}集：{vv.val}；{dd.val}；{ss.val}')
for vv, dd, ss in singular:
    logger.info(f'第{vv.flavor}集：{vv.val}；{dd.val}；{ss.val}')
episodeseq = {int(e)-1 if e.isdecimal() else e for e in args.episode}
doneset = cfg.get('done', set())
try:
    for i, (vv, dd, ss) in enumerate(seq + singular):
        if vv.val in doneset:
            continue
        if len(episodeseq) == 0 or i in episodeseq or any(map(episodeseq.__contains__, vv.flavor)):
            name = os.path.extsep.join((os.path.splitext(vv.val)[0], cfg['tag'], 'ass'))
            with storage.fileout(name) as f:
                ssdoc = ass.toass(ss)
                width, height = ssdoc.play_res_x, ssdoc.play_res_y
                dddoc = ass.toass(dd, width=width, height=height)
                ass.assjoindanmaku(ssdoc, dddoc).dump_file(f)
        doneset.add(vv.val)
finally:
    cfg['done'] = doneset
    cfg.dump()