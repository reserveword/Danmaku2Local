#! /usr/bin/env python3
# -*- encoding:utf-8 -*-


from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from os import path
from typing import Any, Callable, Collection, Dict, Iterable, Iterator, Mapping, MutableSequence, MutableSet, Optional, Sequence, Set, TextIO, Tuple, TypeAlias, TypeVar, overload
import ass
import ffmpeg

from d2l.danmaku2ass import Comment
from d2l.storage import LocalStorage, pathlocal
from d2l.trie import TrieSet
from d2l.util import getint, lcseq

_T = TypeVar('_T')

@dataclass(frozen=True)
class BiliXmlMeta:
    cid: int
    bias: int
    index: str
    title: str
    full: Dict[str, Any]
    patterns: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Tag:
    val: int
    compound: 'TagCompound'
    head: int
    tail: int
    order: int = 0
    # detail: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class SortTag:
    val: str
    flavor: tuple[str, ...]
    compound: 'Optional[TagCompound]' = None
    order: bool = True

@dataclass(frozen=True)
class BiliSortTag(SortTag):
    comments: Iterable[Comment] = field(default_factory=lambda:())

@dataclass(frozen=True)
class XmlSortTag(SortTag):
    pass

@dataclass(frozen=True)
class DummySortTag(SortTag):
    val: str = ''
    flavor: tuple[str, ...] = ()
    compound: 'Optional[TagCompound]' = None

class TagCompound:
    def __init__(self) -> None:
        self.tags: list[Tag] = []
    def __iter__(self) -> Iterator[Tag]:
        return self.tags.__iter__()
    def __getitem__(self, __i: int) -> Tag:
        return self.tags[__i]
    def __len__(self) -> int:
        return len(self.tags)
    def add(self, value: Tag) -> None:
        self.tags.append(value)

class FilenameTagCompound(TagCompound):
    def __init__(self, name: str) -> None:
        super().__init__()
        name = path.basename(name) # filename only
        self.name = name
        self.namenoext, self.nameext = path.splitext(name)
    def build(self):
        head: int = -1
        for i, c in enumerate(self.name):
            if head == -1:
                if c in '0123456789':
                    head = i
            else:
                if c not in '0123456789':
                    self.add(Tag(int(self.name[head:i]), self, head, i))
                    head = -1
        if head != -1:
            self.add(Tag(int(self.name[head:]), self, head, len(self.name)))

class VideoTagCompound(FilenameTagCompound):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.ffprobe = ffmpeg.probe(pathlocal(name))
        streams = self.ffprobe['streams']
        s = defaultdict(list)
        for ss in streams:
            s[ss['codec_type']].append(ss)
        self.video_metas = s['video']
        self.video_meta = s['video'].__iter__().__next__()
        self.resolution = int(self.video_meta['width']), int(self.video_meta['height'])
        self.duration = timedelta(seconds=float(self.ffprobe['format']['duration']))
        if 'subtitle' in s.keys():
            self.subtitles = [SubtitleTagCompound(name, ss, self) for ss in s['subtitle']]
        else:
            self.subtitles = None

class SubtitleTagCompound(FilenameTagCompound):
    @overload
    def __init__(self, name: str) -> None: ...
    @overload
    def __init__(self, name: str, meta: dict[str, Any], video: VideoTagCompound) -> None: ...
    def __init__(self, name: str, meta: Optional[dict[str, Any]] = None, video: Optional[VideoTagCompound] = None) -> None:
        super().__init__(name)
        if meta is not None:
            self.meta = meta
            if video is not None:
                self.video = video

class DanmakuTagCompound(TagCompound):
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, meta: BiliXmlMeta, comments: Iterable[Comment]) -> None: ...
    def __init__(self, meta: Optional[BiliXmlMeta] = None, comments: Optional[Iterable[Comment]] = None) -> None:
        super().__init__()
        if meta is not None:
            assert comments is not None
            self.meta = meta
            self.comments = comments
            self.idx = Tag(getint(meta.index), self, 0, 0)
            self.bias = Tag(meta.bias + 1, self, 0, 0, order = 1)
            self.tags.append(self.idx)
            self.tags.append(self.bias)

class DanmakuFileTagCompound(DanmakuTagCompound, FilenameTagCompound):
    def __init__(self, name: str):
        FilenameTagCompound.__init__(self, name)

def buildtrie(tags: list[Tag], tagextract: Callable[[Tag], str], ref: Optional[TrieSet] = None) -> TrieSet:
    t = TrieSet()
    for tag in tags:
        extract = tagextract(tag)
        for i in range(min(len(extract), 16)): # 集数tag不会太长
            sub = extract[i:]
            if ref is not None:
                sub = sub[:ref.char_prefix(sub)]
            if len(sub):
                t.add(sub)
    return t

def sort(comps: Collection[FilenameTagCompound]) -> tuple[tuple[SortTag], tuple[SortTag]]:
    leftextract = lambda tag: tag.compound.namenoext[tag.head-1::-1]
    rightextract = lambda tag: tag.compound.namenoext[tag.tail:]
    r = defaultdict[int, list[Tag]](list[Tag])
    for c in comps:
        c.build()
        for t in c:
            r[t.val].append(t)
    tleft: Optional[TrieSet[str]] = None
    bestleft = (0, 0, '')
    for i in range(1, len(r)+1):
        v = r[i]
        if len(v) == 0:
            break
        newleft = buildtrie(v, leftextract, tleft)
        if len(newleft):
            tleft = newleft
            ls = ''
            for s in tleft:
                if len(s) > len(ls):
                    ls = s
            if i * len(ls) > bestleft[0]:
                bestleft = (i * len(ls), i, ls[::-1]) # 翻转回来
        else:
            break
    del tleft
    tright: Optional[TrieSet] = None
    bestright = (0, 0, '')
    for i in range(1, len(r)+1):
        v = r[i]
        if len(v) == 0:
            break
        newright = buildtrie(v, rightextract, tright)
        if len(newright):
            tright = newright
            ls = ''
            for s in tright:
                if len(s) > len(ls):
                    ls = s
            if i * len(ls) > bestright[0]:
                bestright = (i * len(ls), i, ls)
        else:
            break
    del tright
    # 接下来要统计每个视频（也就是每个compound）出现在第几集。
    # 考虑到一个序号可能有多个候选视频，
    # 我们优先选出只有一个候选视频的集数，然后把这集从其他集的候选列表中删去
    # 因为Tag相关的类很难作为key，我们使用迭代的序号代替
    bucket: dict[int, list[tuple[int, SortTag]]] = defaultdict(list) # {集数: [(compound, tag)]}
    revdict: dict[int, list[int]] = {} # {compound: [集数]}
    # 剩下的是只有flavor，不占序号的单独集数
    singulars: dict[int, SortTag] = {} # {compound: tag}
    bleft = bestleft[2]
    bright = bestright[2]
    blen = max(bestleft[1], bestright[1])
    broken = bestleft[1] != bestright[1] # 是否出现不能同时匹配两边的情况，如果预期集数不一样说明肯定不能匹配
    if not broken:
        for i, comp in enumerate(comps):
            name = comp.namenoext
            buckets: list[int] = []
            for tag in comp.tags:
                if tag.val > blen: # tag标记的集数已经大于预期的最大集数
                    continue
                fl = name.find(bleft, 0, tag.head)
                fr = name.find(bright, tag.tail)
                if fl == -1 or fr == -1:
                    continue
                buckets.append(tag.val)
                lflavor = name[fl + len(bleft):tag.head]
                rflavor = name[tag.tail:fr]
                bucket[tag.val].append((i, SortTag(comp.name, (lflavor, rflavor), compound=comp)))
            fl = name.find(bleft)
            fr = name.find(bright, fl + len(bleft))
            if fl != -1 and fr != -1:
                singulars[i] = SortTag(comp.name, (name[fl+len(bleft):fr],), compound=comp, order=False)
            revdict[i] = buckets
    if broken or len(bucket) != blen: # 匹配不成功
        bucket.clear()
        revdict.clear()
        if bestleft[0] < bestright[0]:
            # 以左边为主
            blen = bestleft[1]
            for i, comp in enumerate(comps):
                name = comp.namenoext
                buckets: list[int] = []
                for tag in comp.tags:
                    if tag.val > blen: # tag标记的集数已经大于预期的最大集数
                        continue
                    fl = name.find(bleft, 0, tag.head)
                    if fl == -1:
                        continue
                    buckets.append(tag.val)
                    lflavor = name[fl + len(bleft):tag.head]
                    rflavor = name[tag.tail:tag.tail + 3] # 固定长度rflavor
                    bucket[tag.val].append((i, SortTag(comp.name, (lflavor, rflavor), compound=comp)))
                fl = name.find(bleft)
                if fl != -1: # 固定长度flavor
                    singulars[i] = SortTag(comp.name, (name[fl+len(bleft):fl+len(bleft)+3],), compound=comp, order=False)
                revdict[i] = buckets
        else:
            # 以右边为主
            blen = bestright[1]
            for i, comp in enumerate(comps):
                name = comp.namenoext
                buckets: list[int] = []
                for tag in comp.tags:
                    if tag.val > blen: # tag标记的集数已经大于预期的最大集数
                        continue
                    fr = name.find(bright, tag.tail)
                    if fr == -1:
                        continue
                    buckets.append(tag.val)
                    lflavor = name[tag.head - 3:tag.head] # 固定长度lflavor
                    rflavor = name[tag.tail:fr]
                    bucket[tag.val].append((i, SortTag(comp.name, (lflavor, rflavor), compound=comp)))
                fr = name.find(bright)
                if fr != -1: # 固定长度flavor
                    singulars[i] = SortTag(comp.name, (name[fr-3:fr],), compound=comp, order=False)
                revdict[i] = buckets
    out: dict[int, SortTag] = {}
    while len(bucket):
        edge = []
        for k, v in bucket.items():
            if len(v) == 1:
                edge.append(k)
        for k in edge:
            v = bucket.pop(k)
            i, t = v[0]
            out[k] = t
            # 删除bucket所有值列表里首项为i的元组（del bucket[*][*] if bucket[*][*] == (i, *)）
            for kk in revdict[i]: # 只有bucket[kk]里才会有这样的数据
                for ii, vv in enumerate(bucket[kk]):
                    if vv[0] == i:
                        del bucket[kk][ii]
                        if len(bucket[kk]) == 0:
                            del bucket[kk]
            # 肯定也不是单独集数
            del singulars[i]
        if len(edge) == 0: # 没有候选视频唯一的集数了
            break
    if len(out) < blen: # 如果有些集数还没确定下来
        # 统计确定下来的集数里面lflavor的最后一个字符和rflavor的第一个字符（也就是集数前后字符）出现频率（包括''）
        lcount = Counter()
        rcount = Counter()
        for v in out.values():
            lflavor, rflavor = v.flavor
            if lflavor == '':
                lcount[''] += 1
            else:
                lcount[lflavor[-1]] += 1
            if rflavor == '':
                rcount[''] += 1
            else:
                rcount[rflavor[-1]] += 1
        for i in range(blen, 0, -1):
            if i not in out:
                besttag = None
                bestcomp = None
                bestscore = (-1, 0)
                for compid, tag in bucket[i]:
                    score = 0
                    rank = LanguageRank.multirank(tag.val, sep=path.extsep)
                    lflavor, rflavor = tag.flavor
                    if lflavor == '':
                        score += lcount['']
                    else:
                        score += lcount[lflavor[-1]]
                    if rflavor == '':
                        score += rcount['']
                    else:
                        score += rcount[rflavor[-1]]
                    if (score, rank) > bestscore:
                        bestcomp = compid
                        besttag = tag
                        bestscore = (score, rank)
                # 任何score都肯定大于-1，bucket[i]（大概）不会是空的吧
                # TODO 这部分代码确实有问题，没考虑到候选视频唯一的集数有可能共用compound（也就是说，一个视频同时是两集的唯一候选）
                assert bestcomp is not None
                assert besttag is not None
                # 删除bucket所有值列表里首项为i的元组（del bucket[*][*] if bucket[*][*] == (i, *)）
                for kk in revdict[bestcomp]: # 只有bucket[kk]里才会有这样的数据
                    for ii, vv in enumerate(bucket[kk]):
                        if vv[0] == i:
                            del bucket[kk][ii]
                            if len(bucket[kk]) == 0:
                                del bucket[kk]
                # 肯定也不是单独集数
                del singulars[bestcomp]
                out[i] = besttag
    return tuple(out[i] for i in range(1, blen+1)), tuple(singulars.values())

class LanguageRank:
    CHINESE = 1
    CHINESE_SURE = 2
    SIMPLIFIED = 4
    SIMPLIFIED_SURE = 8
    TRADITIONAL = 16
    CHINESE_TAGS = {'ch', 'chi', 'chn', 'chs', 'cn', 'zh', 'zhs', 'sc', 'chinese', 'zh-cn', 'zh-hans', 'hans', '中文', '汉语', '中', '文', '汉'}
    SIMPLIFIED_TAGS = {'simplified', 'zh-cn', 'zh-hans', 'sc', 'chs', 'zhs', 'hans', '简体', '简'}
    TRADITIONAL_TAGS = {'traditional', 'tc', 'tw', 'hk', 'hant', '繁', '體', '漢'}
    @staticmethod
    def rank(s: str):
        s = s.lower()
        r = 0
        for t in LanguageRank.CHINESE_TAGS:
            if t in s:
                r |= LanguageRank.CHINESE
                if len(s) < 3 * len(t):
                    r |= LanguageRank.CHINESE_SURE
        for t in LanguageRank.SIMPLIFIED_TAGS:
            if t in s:
                r |= LanguageRank.SIMPLIFIED
                if len(s) < 3 * len(t):
                    r |= LanguageRank.SIMPLIFIED_SURE
        for t in LanguageRank.TRADITIONAL_TAGS:
            if t in s:
                r -= LanguageRank.TRADITIONAL
                break
        return r
    @staticmethod
    def multirank(s: str, split:Callable[[str], Iterable[str]]=str.split, *args, **kwargs):
        return tuple(sorted(map(LanguageRank.rank, split(s, *args, **kwargs)), reverse=True))

def match_subtitle_video(v: Collection[TagCompound], s: Collection[TagCompound]) -> Collection[tuple[SubtitleTagCompound, VideoTagCompound]]:
    # 判断字幕是否从视频里剥离出来，或者是否与视频同名
    # 顺序依次为：从视频里剥离出来、与视频同名、与视频只有扩展名不同、与视频只有扩展名和标签（二级扩展名/N级扩展名）不同，且标签不是弹幕标签
    # 其中除第二种之外其他情况内部可能有顺序关系
    # 1. 从视频里剥离出来
    t = defaultdict(list[SubtitleTagCompound])
    vt: Collection[VideoTagCompound] = v # type: ignore
    st: Collection[SubtitleTagCompound] = s # type: ignore
    for k in st:
        if hasattr(k, 'video'):
            t[(k.meta['tags']['language'].lower(), k.meta['tags']['title'].lower())].append(k)
    if t:
        # 视频是包含字幕的，（如果没有额外要求）可以直接使用这里的字幕
        # 至少需要80%的视频有这类型的字幕，避免有的类型只有少数视频有，结果不处理剩下的字幕的情况
        threshold = max(map(len, t.values())) * 0.8
        tt = {k:v for k, v in t.items() if len(v) >= threshold}
        kmax = max(tt.keys(), key=lambda x:max(map(LanguageRank.rank, x)))
        return [(c, c.video) for c in t[kmax]]
    # 2. 与视频同名
    # 3. 与视频只有扩展名不同
    threshold = len(v) * 0.8
    videonames = {vv.name: vv for vv in vt}
    videonamesnoext = {vv.namenoext: vv for vv in vt}
    results = defaultdict[str,dict](dict)
    for k in st:
        if k.name in videonames:
            results[''][k.name] = k
        elif k.namenoext in videonamesnoext:
            results[k.nameext][k.namenoext] = k
    if len(results['']) > threshold: # 2. 与视频同名
        return [(k, videonames[name]) for name, k in results[''].items()]
    if len(results['.ass']) > threshold: # 3. 与视频只有扩展名不同（ass优先）
        return [(k, videonamesnoext[name]) for name, k in results['.ass'].items()]
    res = max(results.values(), key=len) # 3. 与视频只有扩展名不同
    if len(res) > threshold:
        return [(k, videonamesnoext[name]) for name, k in res.items()]
    # 4. 与视频只有扩展名和标签（二级扩展名/N级扩展名）不同，且标签不是弹幕标签
    subtitlenames = {kk.namenoext: kk for kk in st}
    results = defaultdict[str,dict](dict)
    vi = iter(sorted(videonamesnoext.keys()))
    vl: Optional[str] = None
    for k in sorted(subtitlenames.keys()):
        if vl is not None and k.startswith(vl) and len(k) > len(vl) and k[len(vl)] == '.':
            token = k[len(vl) + 1:]
            results[token][vl] = k
        else:
            if vl is None or vl < k:
                try:
                    vl = next(vi)
                except StopIteration:
                    break
    for vv in sorted(results.keys(), key=LanguageRank.rank, reverse=True): # 按二级扩展名排序，取第一个满足threshold的
        r = results[vv]
        if len(r) >= threshold:
            return [(subtitlenames[sname], videonamesnoext[vname]) for vname, sname in r.items()]
    return []

@overload
def combine(extra: Sequence[SortTag], base: Sequence[SortTag]) -> dict[SortTag, SortTag]: ...
@overload
def combine(extra: Collection[SortTag], base: Collection[SortTag]) -> dict[SortTag, SortTag]: ...
def combine(extra: Collection[SortTag], base: Collection[SortTag]) -> dict[SortTag, SortTag]:
    ordered = isinstance(extra, Sequence) and isinstance(base, Sequence)
    if ordered:
        for e in extra:
            if not e.order:
                ordered = False
                break
    if ordered:
        for b in base:
            if not b.order:
                ordered = False
                break
    if ordered:
        # ordered
        return {b:e for b, e in zip(base, extra)}
    else:
        # singular
        r = {}
        for b in base:
            best = None
            bestscore = (0, (0,), 0) # 公共串长度，语言tag匹配，-串长度
            for bflavor in b.flavor:
                for e in extra:
                    for eflavor in e.flavor:
                        score = (len(lcseq(eflavor, bflavor)), LanguageRank.multirank(e.val, sep=path.extsep), len(extra))
                        if score > bestscore:
                            best = e
                            bestscore = score
            if best is None:
                break
            r[b] = best
        return r

@overload
def match(v: Collection[VideoTagCompound], d: Collection[DanmakuTagCompound], s: Collection[SubtitleTagCompound]) -> tuple[list[tuple[SortTag, SortTag, SortTag]], list[tuple[SortTag, SortTag, SortTag]]]: ...
@overload
def match(v: Collection[VideoTagCompound], d: Collection[DanmakuTagCompound]) -> tuple[list[tuple[SortTag, SortTag]], list[tuple[SortTag, SortTag]]]: ...
def match(v: Collection[VideoTagCompound], d: Collection[DanmakuTagCompound], s: Optional[Collection[SubtitleTagCompound]] = None) -> tuple[list[tuple[SortTag, SortTag, SortTag]], list[tuple[SortTag, SortTag, SortTag]]] | tuple[list[tuple[SortTag, SortTag]], list[tuple[SortTag, SortTag]]]:
    if s is None: # 没有字幕（比如嵌进视频里无法分离出来了）
        seq, singulars = sort(v)
        mapping: dict[SortTag, SortTag] = defaultdict(DummySortTag)
    else:
        tag = path.extsep + LocalStorage()['tag']
        s = [ss for ss in s if not ss.namenoext.endswith(tag)]
        svmatch = match_subtitle_video(v, s)
        if len(svmatch) == 0:
            seq, singulars = sort(v)
            sseq, ssingulars = sort(s)
            mapping: dict[SortTag, SortTag] = defaultdict(DummySortTag)
            mapping.update(combine(ssingulars, singulars))
            mapping.update(combine(sseq, seq))
        else:
            mappingname = {vv.name: ss.name for ss, vv in svmatch}
            v = [vv for ss, vv in svmatch]
            seq, singulars = sort(v)
            mapping: dict[SortTag, SortTag] = defaultdict(DummySortTag)
            mapping.update({vv:SortTag(mappingname[vv.val], (), None, vv.order) for vv in singulars})
            mapping.update({vv:SortTag(mappingname[vv.val], (), None, vv.order) for vv in seq})
    dfile = [dd for dd in d if isinstance(dd, DanmakuFileTagCompound)]
    dmeta = [dd for dd in d if not isinstance(dd, DanmakuFileTagCompound)]
    if len(dmeta) == 0:
        dseq, dsingulars = sort(dfile)
        dseq = [XmlSortTag(dd.val, dd.flavor, None, dd.order) for dd in dseq]
        dsingulars = [XmlSortTag(dd.val, dd.flavor, None, dd.order) for dd in dsingulars]
    else:
        dsort = {dd.idx.val: dd for dd in dmeta}
        dseq = []
        dsingulars = set()
        for k in range(len(dsort) + 1):
            if k not in dsort:
                break
            dd = dsort.pop(k)
            dseq.append(BiliSortTag(str(dd.meta.cid), (dd.meta.title, dd.meta.index), comments=dd.comments))
        for dd in dsort.values():
            dsingulars.add(BiliSortTag(str(dd.meta.cid), (dd.meta.title, dd.meta.index), comments=dd.comments, order=False))
    dmapping: dict[SortTag, SortTag] = defaultdict(DummySortTag)
    dmapping.update(combine(dsingulars, singulars))
    dmapping.update(combine(dseq, seq))
    # seq, singulars, mapping, dmapping
    return [(vv, dmapping[vv], mapping[vv]) for vv in seq], [(vv, dmapping[vv], mapping[vv]) for vv in singulars]