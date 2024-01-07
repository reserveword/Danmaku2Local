from collections import defaultdict
from dataclasses import dataclass
import os
import random
import re
from typing import Collection, Optional

import ass
import ffmpeg

from mixsub.schema.models import Subtitle, SubtitleSeries, _AssEventType
from mixsub.storage import filein, fileout, pathlocal
from mixsub.util import FileType, LocalFile, NeedResize, thisdir


@dataclass
class LocalSubtitleSeries(SubtitleSeries):
    """本地字幕系列"""
    path: Optional[str] = None
    _subtitles: Optional[list['Subtitle']] = None

    def subtitles(self):
        if not self._subtitles:
            self._subtitles = [LocalSubtitle(v) for v in thisdir(FileType.SUBTITLE, self.path)]
        return self._subtitles


@dataclass
class LocalSubtitle(LocalFile, Subtitle):
    """单个本地字幕文件"""
    _document: Optional[ass.Document] = None

    def document(self) -> ass.Document:
        if not self._document:
            with filein(self.path) as f:
                self._document = ass.parse_file(f)
        return self._document

@dataclass
class LocalVideoSubtitleSeries(SubtitleSeries):
    """本地视频附加的字幕系列"""
    path: Optional[str] = None
    _subtitles: Optional[list['Subtitle']] = None

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
    """单个本地视频附加的单个字幕"""
    meta: dict
    _document: Optional[ass.Document] = None

    def index(self) -> str:
        return self.meta.get('index', 's:0')

    def document(self) -> ass.Document:
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



def ass_out(path: str, doc: ass.Document):
    with fileout(os.extsep.join((path, 'ass')), 'w') as f:
        doc.dump_file(f)
