

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
import os
from typing import Collection, Iterable, List, Optional

import ass

from mixsub import subtitle
from mixsub.storage import fileout
from mixsub.util import LocalFile, thisdir, FileType


class VideoSeries(metaclass=ABCMeta):
    @abstractmethod
    def videos(self) -> Iterable['Video']:
        ...


class Video(metaclass=ABCMeta):
    name: str
    pathname: str
    basename: str
    extname: str


@dataclass
class LocalVideoSeries(VideoSeries):
    path: Optional[str] = None
    _videos: Optional[List['LocalVideo']] = None

    def videos(self):
        if not self._videos:
            self._videos = [LocalVideo(v) for v in thisdir(FileType.VIDEO, self.path)]
        return self._videos


@dataclass
class LocalVideo(LocalFile, Video):
    pass


def ass_out(path: str, doc: ass.Document, mix: Collection[ass.line._Line]):
    with fileout(os.extsep.join((path, 'ass')), 'w') as f:
        subtitle.assjoin(doc, mix).dump_file(f)
