

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
import os
from typing import Collection, Iterable, List, Optional

import ass

from mixsub import subtitle
from mixsub.schema.models import Video, VideoSeries
from mixsub.storage import fileout
from mixsub.util import LocalFile, thisdir, FileType


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
