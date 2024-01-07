from abc import ABCMeta, abstractmethod
from collections import defaultdict
from datetime import timedelta
import os
import random
import re
from ass import Document, Style, line as assline
from dataclasses import dataclass
from typing import Collection, Generic, Iterable, List, Optional, TypeAlias, TypeVar

import ass
import ffmpeg
from mixsub.storage import filein, pathlocal
from mixsub.util import FileType, LocalFile, NeedResize, thisdir

_AssEventType: TypeAlias = (
    assline.Dialogue
    | assline.Comment
    | assline.Picture
    | assline.Sound
    | assline.Movie
    | assline.Command
)

_T = TypeVar('_T')

class SubtitleSeries(metaclass=ABCMeta):
    @abstractmethod
    def subtitles(self) -> Iterable['Subtitle']:
        ...


class Subtitle(metaclass=ABCMeta):
    name: str
    pathname: str
    basename: str
    @abstractmethod
    def document(self) -> ass.Document:
        ...



@dataclass
class LocalSubtitleSeries(SubtitleSeries):
    path: Optional[str] = None
    _subtitles: Optional[List['Subtitle']] = None

    def subtitles(self):
        if not self._subtitles:
            self._subtitles = [LocalSubtitle(v) for v in thisdir(FileType.SUBTITLE, self.path)]
        return self._subtitles


@dataclass
class LocalSubtitle(LocalFile, Subtitle):
    _document: Optional[ass.Document] = None

    def document(self) -> Document:
        if not self._document:
            with filein(self.path) as f:
                self._document = ass.parse_file(f)
        return self._document

@dataclass
class LocalVideoSubtitleSeries(SubtitleSeries):
    path: Optional[str] = None
    _subtitles: Optional[List['Subtitle']] = None

    def subtitles(self):
        if not self._subtitles:
            subtitles = []
            for v in thisdir(FileType.VIDEO, self.path):
                ffprobe = ffmpeg.probe(pathlocal(v))
                streams = ffprobe['streams']
                s = defaultdict(list)
                for ss in streams:
                    s[ss['codec_type']].append(ss)
                if 'subtitle' in s.keys():
                    subtitles.append(LocalVideoSubtitle(v, ss) for ss in s['subtitle'])
            self._subtitles = subtitles
        return self._subtitles


@dataclass
class LocalVideoSubtitle(LocalFile, Subtitle):
    meta: dict
    _document: Optional[ass.Document] = None

    def index(self) -> str:
        return self.meta.get('index', 's:0')

    def document(self) -> Document:
        if not self._document:
            stream_idx_path = str(self.index()).replace(':', os.extsep)
            dirname, basename = os.path.split(self.path)
            pathpattern = os.extsep.join((re.escape(basename), re.escape(stream_idx_path), '[0-9a-fA-F]{8}', 'ass'))
            for file in os.listdir(dirname):
                if re.fullmatch(pathpattern, os.path.basename(file)):
                    path = file
                    break
            else:
                path = os.extsep.join((self.path, stream_idx_path, random.randbytes(8).hex(), 'ass'))
                ffmpeg.input(self.path)[str(self.index())].output(path, f='ass').run()
            with filein(path) as f:
                self._document = ass.parse_file(f)
        return self._document

@dataclass
class AssLine(Generic[_T]):
    line: _T

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, AssLine) or type(__o) is not type(self):
            return False
        return frozenset(self.line.__dict__.items()) == frozenset(__o.line.__dict__.items())

    def __hash__(self) -> int:
        return frozenset(self.line.__dict__.items()).__hash__()


def assjoin(doc: Document, mix: Collection[ass.line._Line]) -> Document:
    for line in mix:
        if isinstance(line, NeedResize):
            try:
                width, height = doc.play_res_x, doc.play_res_y
            except:
                width, height = 1920, 1080
            line.resize(width, height)
        if isinstance(line, _AssEventType):
            doc.events.append(line)
        elif isinstance(line, ass.Style):
            doc.styles.append(line)
    return doc
