from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
import os
from typing import Annotated, Iterable, Optional
from mixsub.subtitle import Subtitle
from mixsub.util import MixSourceSet

from mixsub.videos import Video

# @dataclass
class MatchedVideo:
    # video: Video # type: ignore[override]
    # subtitle: Optional[Subtitle] = None # type: ignore[override]
    # mixes: Optional[MixSourceSet] = None # type: ignore[override]
    # index: Optional[int] = None # type: ignore[override]
    def __init__(self, video, subtitle=None, mixes=None, index=None) -> None:
        self.video = video
        if subtitle is not None:
            self.subtitle = subtitle
        if mixes is not None:
            self.mixes = mixes
        if index is not None:
            self.index = index

    @property
    def video(self) -> Video:
        return self._video

    @video.setter
    def video(self, video: Video):
        self._video = video

    @property
    def subtitle(self) -> Subtitle:
        return self._subtitle

    @subtitle.setter
    def subtitle(self, subtitle: Subtitle):
        self._subtitle = subtitle

    @property
    def mixes(self) -> MixSourceSet:
        return self._mixes

    @mixes.setter
    def mixes(self, mixes: MixSourceSet):
        self._mixes = mixes

    def basepath(self) -> str:
        return os.extsep.join((os.path.join(self.video.pathname, self.video.basename), self.mixes.tag))



class Matcher(metaclass=ABCMeta):
    @abstractmethod
    def __call__(
        self,
        videos: Iterable[Video],
        subtitles: Iterable[Subtitle],
        mixes: Iterable[MixSourceSet],
    ) -> Iterable[MatchedVideo]:
        ...
