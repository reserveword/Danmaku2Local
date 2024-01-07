

from dataclasses import dataclass
from typing import Optional


from mixsub.schema.models import Video, VideoSeries
from mixsub.util import LocalFile, thisdir, FileType


@dataclass
class LocalVideoSeries(VideoSeries):
    path: Optional[str] = None
    _videos: Optional[list['LocalVideo']] = None

    def videos(self):
        if not self._videos:
            self._videos = [LocalVideo(v) for v in thisdir(FileType.VIDEO, self.path)]
        return self._videos


@dataclass
class LocalVideo(LocalFile, Video):
    pass
