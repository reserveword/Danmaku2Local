from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Collection, Iterable, Optional, TypeAlias

import ass

# mixsource part


class MixSourceSeries(metaclass=ABCMeta):
    """混入字幕的数据源系列"""
    @abstractmethod
    def code(self) -> str:
        """数据源标识符"""

    @abstractmethod
    def expand(self) -> Iterable['MixSourceSet']:
        """展开数据源列表"""


class MixSourceSet(metaclass=ABCMeta):
    """混入单个字幕的数据源"""

    tag: str

    @abstractmethod
    def code(self) -> str:
        """数据源标识符"""

    @abstractmethod
    def index(self) -> int:
        """数据源在系列中的序号"""

    @abstractmethod
    def sources(self) -> Collection[ass.line._Line]:
        """数据源内容"""


# subtitle part

_AssEventType: TypeAlias = (
    ass.line.Dialogue
    | ass.line.Comment
    | ass.line.Picture
    | ass.line.Sound
    | ass.line.Movie
    | ass.line.Command
)


class SubtitleSeries(metaclass=ABCMeta):
    """字幕系列"""
    @abstractmethod
    def subtitles(self) -> Iterable['Subtitle']:
        """提取字幕系列中的每一份字幕"""


class Subtitle(metaclass=ABCMeta):
    """单个视频的字幕"""
    name: str
    pathname: str
    basename: str

    @abstractmethod
    def document(self) -> ass.Document:
        """将字幕转为ass文档格式"""


# video part


class VideoSeries(metaclass=ABCMeta):
    """视频系列"""
    @abstractmethod
    def videos(self) -> Iterable['Video']:
        """系列中的视频列表"""


class Video(metaclass=ABCMeta):
    """单个视频"""
    name: str
    pathname: str
    basename: str
    extname: str


# matcher part

@dataclass
class MatchedVideo(metaclass=ABCMeta):
    """一组待合并字幕的视频，包括视频、字幕、附加数据源，以及当前集数"""

    video: Video
    subtitle: Optional[Subtitle] = None
    mixes: Optional[MixSourceSet] = None
    index: Optional[int] = None



class Matcher(metaclass=ABCMeta):
    @abstractmethod
    def __call__(
        self,
        videos: Iterable[Video],
        subtitles: Iterable[Subtitle],
        mixes: Iterable[MixSourceSet],
    ) -> Iterable[MatchedVideo]:
        ...
