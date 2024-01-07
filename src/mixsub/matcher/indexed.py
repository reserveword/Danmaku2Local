

from collections import defaultdict
from typing import Collection, Iterable, Optional, Protocol, TypeVar
from mixsub.matcher import MatchedVideo, Matcher
from mixsub.subtitle import LocalVideoSubtitle, Subtitle
from mixsub.videos import Video

class IndexedMatcher(Matcher):
    def __call__(self, videos, subtitles, mixes):
        videos = [MatchedVideo(video, index=i) for i, video in enumerate(sort(list(videos)))]
        subtitles = list(subtitles)
        mixes = list(mixes)
        fail_count = 0
        for video in videos:
            subtitle: Subtitle | None = match_max(video.video, subtitles)
            if subtitle:
                video.subtitle = subtitle
            else:
                fail_count += 1
        if fail_count:
            subtitles = sort(subtitles)
            for video, subtitle in zip(videos, subtitles):
                video.subtitle = subtitle
        for video, mix in zip(videos, mixes):
            video.mixes = mix
        return videos

_T_Video_Subtitle = TypeVar('_T_Video_Subtitle', Video, Subtitle)

def sort(items: Collection[_T_Video_Subtitle]) -> Iterable[_T_Video_Subtitle]:
    bestmatch = ()
    thisoffset = -1
    while True:
        thisoffset += 1
        resultset: dict[str, dict[int, _T_Video_Subtitle]] = defaultdict(dict)
        resultrank: dict[str, dict[int, int]] = defaultdict(dict)
        end = True
        for item in items:
            name = item.basename
            if len(name) > thisoffset:
                end = False
            else:
                break
            if name[thisoffset] not in '0123456789':
                continue
            thisidx = 0
            for char in name[thisoffset:]:
                if char in '0123456789':
                    thisidx = thisidx * 10 + (ord(char) - ord('0'))
                else:
                    break
            matchrank = language_rank(item)
            if thisidx not in resultrank[name[:thisoffset]] or resultrank[name[:thisoffset]][thisidx] < matchrank:
                resultrank[name[:thisoffset]][thisidx] = matchrank
                resultset[name[:thisoffset]][thisidx] = item
        if end:
            break
        for _, results in resultset.items():
            matches = []
            for i in range(len(results) + 1):
                if i in results:
                    matches.append(results[i])
            if len(bestmatch) <= len(matches):
                bestmatch = matches
    return bestmatch


CHINESE_TAGS = {'ch', 'chi', 'chn', 'chs', 'cn', 'zh', 'zhs', 'sc', 'chinese', 'zh-cn', 'zh-hans', 'hans', '中文', '汉语', '中', '文', '汉'}
SIMPLIFIED_TAGS = {'simplified', 'zh-cn', 'zh-hans', 'sc', 'chs', 'zhs', 'hans', '简体', '简', 'gb'}
TRADITIONAL_TAGS = {'traditional', 'tc', 'tw', 'hk', 'hant', '繁', '體', '漢', 'big5'}
def havetag(subtitle: _T_Video_Subtitle, target: set[str]) -> bool:
    name: str = subtitle.name.lower()
    for t in target:
        if t in name:
            return True
    if not isinstance(subtitle, LocalVideoSubtitle):
        return False
    tags: dict[str, str] = subtitle.meta.get('tags', {})
    lang: str = tags.get('language', '').lower()
    for t in target:
        if t in lang:
            return True
    title: str = tags.get('title', '').lower()
    for t in target:
        if t in title:
            return True
    return False

class SubtitleTest(Protocol):
    def __call__(self, video: Video, subtitle: Subtitle) -> bool:
        ...

FullnameMatchTest: SubtitleTest = lambda video, subtitle: video.name == subtitle.name
BasenameMatchTest: SubtitleTest = lambda video, subtitle: video.basename == subtitle.basename
BasenamePrefixTest: SubtitleTest = lambda video, subtitle: subtitle.basename.startswith(video.basename)
SimpTagTest: SubtitleTest = lambda video, subtitle: havetag(subtitle, SIMPLIFIED_TAGS)
ChnTagTest: SubtitleTest = lambda video, subtitle: havetag(subtitle, CHINESE_TAGS)
TradTagTest: SubtitleTest = lambda video, subtitle: not havetag(subtitle, TRADITIONAL_TAGS)

TEST_RANK: list[SubtitleTest] = [FullnameMatchTest, BasenameMatchTest, BasenamePrefixTest, SimpTagTest, ChnTagTest, TradTagTest]
TEST_THRESHOLD: list[SubtitleTest] = [FullnameMatchTest, BasenameMatchTest, BasenamePrefixTest]

def match_rank_threshold(video: Video, subtitle: Subtitle) -> int:
    result = 0
    threshold = False
    for test in TEST_RANK:
        result *= 2
        if test(video, subtitle):
            result |= 1
            if test in TEST_THRESHOLD:
                threshold = True
    return result if threshold else 0

def match_max(video: Video, subtitles: Iterable[Subtitle]) -> Optional[Subtitle]:
    chosen = None
    chosen_rank = 0
    for subtitle in subtitles:
        rank = match_rank_threshold(video, subtitle)
        if rank > chosen_rank:
            chosen = subtitle
            chosen_rank = rank
    return chosen

class SubtitleLanguageTest(Protocol):
    def __call__(self, subtitle: _T_Video_Subtitle) -> bool:
        ...

SimpLanguageTest: SubtitleLanguageTest = lambda subtitle: havetag(subtitle, SIMPLIFIED_TAGS)
ChnLanguageTest: SubtitleLanguageTest = lambda subtitle: havetag(subtitle, CHINESE_TAGS)
TradLanguageTest: SubtitleLanguageTest = lambda subtitle: not havetag(subtitle, TRADITIONAL_TAGS)

TEST_LANGUAGE: list[SubtitleLanguageTest] = [SimpLanguageTest, ChnLanguageTest, TradLanguageTest]

def language_rank(subtitle: _T_Video_Subtitle) -> int:
    result = 0
    for test in TEST_LANGUAGE:
        if test not in TEST_THRESHOLD and test(subtitle):
            result += (1 << TEST_LANGUAGE.index(test))
    return result
