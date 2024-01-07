"""系列匹配相关"""

import os

from mixsub.schema.models import MatchedVideo


def tagged_name(spec: MatchedVideo):
    """系列匹配后用混入部分的tag追加命名"""
    if spec.mixes is None:
        raise ValueError('incomplete matched video: mixes missing')
    return os.extsep.join(
            (os.path.join(spec.video.pathname, spec.video.basename), spec.mixes.tag)
        )
